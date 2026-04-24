from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from fastapi.responses import StreamingResponse
from io import BytesIO
from datetime import datetime
from typing import List
import os

try:
    from fpdf import FPDF
    _fpdf_import_error = None
except Exception as e:  # pragma: no cover
    FPDF = None
    _fpdf_import_error = e

from app.models.holiday import Holiday, HolidayCreate, HolidayUpdate
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.holiday_service import HolidayService, get_holiday_service
from app.services.activity_log_service import ActivityLogService, get_activity_log_service
from app.models.activity_log import ActivityLogCreate


router = APIRouter()


@router.get("/", response_model=List[Holiday])
async def list_holidays(
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
):
    return await holiday_service.get_all_holidays()


@router.get("/download-pdf")
async def download_holidays_pdf(
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    year: int | None = Query(default=None),
):
    holidays = await holiday_service.get_all_holidays()

    if year is not None:
        holidays = [
            h
            for h in (holidays or [])
            if getattr(h, "date", None)
            and str(getattr(h, "date"))[:4].isdigit()
            and int(str(getattr(h, "date"))[:4]) == int(year)
        ]

    def _pdf_escape_text(value: str) -> str:
        return (
            str(value or "")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    def _build_minimal_pdf(lines: List[str]) -> bytes:
        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

        # A4 in points: 595 x 842
        font_obj = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

        # Build text stream
        x = 48
        y = 800
        leading = 14
        parts: List[bytes] = []
        parts.append(b"BT\n")
        parts.append(f"/F1 12 Tf\n{x} {y} Td\n".encode("ascii"))
        for i, raw in enumerate(lines):
            t = _pdf_escape_text(raw)
            parts.append(f"({t}) Tj\n".encode("utf-8"))
            if i != len(lines) - 1:
                parts.append(f"0 -{leading} Td\n".encode("ascii"))
        parts.append(b"ET\n")
        text_stream = b"".join(parts)
        contents_obj = (
            b"<< /Length "
            + str(len(text_stream)).encode("ascii")
            + b" >>\nstream\n"
            + text_stream
            + b"endstream"
        )

        # Objects
        objs: List[bytes] = []
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objs.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        objs.append(font_obj)
        objs.append(contents_obj)

        # Write file with xref
        out = bytearray()
        out += header
        offsets = [0]
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode("ascii")
            out += body
            out += b"\nendobj\n"

        xref_start = len(out)
        out += b"xref\n"
        out += f"0 {len(offsets)}\n".encode("ascii")
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += f"{off:010d} 00000 n \n".encode("ascii")

        out += b"trailer\n"
        out += f"<< /Size {len(offsets)} /Root 1 0 R >>\n".encode("ascii")
        out += b"startxref\n"
        out += f"{xref_start}\n".encode("ascii")
        out += b"%%EOF\n"
        return bytes(out)

    def parse_date(value: str):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except Exception:
            try:
                return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
            except Exception:
                return None

    def fmt_pretty(value: str) -> str:
        d = parse_date(value)
        if not d:
            return str(value or "")
        return d.strftime("%a, %-d %b %Y")

    (holidays or []).sort(
        key=lambda h: (
            parse_date(getattr(h, "date", ""))
            or datetime.max.date()
        )
    )

    resolved_year = year
    if resolved_year is None:
        for h in holidays or []:
            d = parse_date(getattr(h, "date", ""))
            if d:
                resolved_year = d.year
                break
    if not resolved_year:
        resolved_year = datetime.utcnow().year

    if FPDF is None:
        err = _fpdf_import_error
        detail = "PDF styling dependency is not available (fpdf2). Please install backend requirements."
        if err is not None:
            detail = f"{detail} Import error: {err}"
        raise HTTPException(status_code=500, detail=detail)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    green = (0, 200, 100)
    navy = (18, 52, 94)
    light_row = (245, 247, 250)
    border = (220, 226, 235)

    # Header logo (W mark) + brand text
    logo_path = None
    try:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
        candidate = os.path.join(root_dir, "office_leave_management_frontend", "src", "wizzgeek.png")
        if os.path.exists(candidate):
            logo_path = candidate
    except Exception:
        logo_path = None

    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*green)

    # If we have the logo file, use it as the "W" and print "IZZGEEKS" next to it.
    # Otherwise fall back to plain text.
    if logo_path:
        try:
            page_w = 210
            y = 18
            logo_w = 14
            gap = 2
            brand_text = "IZZGEEKS"
            text_w = pdf.get_string_width(brand_text)
            lockup_w = logo_w + gap + text_w
            x = (page_w - lockup_w) / 2

            pdf.image(logo_path, x=x, y=y, w=logo_w)
            pdf.set_xy(x + logo_w + gap, y + 1)
            pdf.cell(text_w, 12, brand_text, ln=1)
        except Exception:
            pdf.cell(0, 12, "WIZZGEEKS", ln=1, align="C")
    else:
        pdf.cell(0, 12, "WIZZGEEKS", ln=1, align="C")

    pdf.ln(2)
    pdf.set_text_color(31, 41, 55)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"{resolved_year} Holiday Leave Calendar", ln=1, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 5, "Official Public Holidays", ln=1, align="C")

    pdf.ln(6)

    left_margin = 18
    right_margin = 18
    table_w = 210 - left_margin - right_margin
    col_num = 10
    col_date = 48
    col_name = table_w - col_num - col_date
    row_h = 8

    pdf.set_draw_color(*border)
    pdf.set_fill_color(*navy)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)

    pdf.set_x(left_margin)
    pdf.cell(col_num, row_h, "#", border=1, align="C", fill=True)
    pdf.cell(col_date, row_h, "Date", border=1, align="C", fill=True)
    pdf.cell(col_name, row_h, "Holiday Name", border=1, align="C", fill=True, ln=1)

    pdf.set_text_color(17, 24, 39)
    pdf.set_font("Helvetica", "", 9)
    if not holidays:
        pdf.set_x(left_margin)
        pdf.cell(table_w, row_h, "No holidays found", border=1, align="C")
    else:
        for idx, h in enumerate(holidays, start=1):
            fill = idx % 2 == 0
            if fill:
                pdf.set_fill_color(*light_row)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.set_x(left_margin)
            pdf.cell(col_num, row_h, str(idx), border=1, align="C", fill=fill)
            pdf.cell(col_date, row_h, fmt_pretty(getattr(h, "date", "")), border=1, align="C", fill=fill)
            pdf.cell(col_name, row_h, str(getattr(h, "name", "") or ""), border=1, align="L", fill=fill, ln=1)

    pdf.ln(8)
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "* This calendar is for reference purposes only. Actual leave entitlements are subject to company policy.")

    pdf_bytes = bytes(pdf.output(dest="S"))
    buf = BytesIO(pdf_bytes)
    filename = f"holidays_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)


@router.post("/", response_model=Holiday)
async def create_holiday(
    holiday: HolidayCreate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    try:
        created = await holiday_service.create_holiday(holiday)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="holiday_created",
            title="Holiday created",
            description=f"{actor_name} created a holiday: {created.name}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="holiday",
            entity_id=str(created.id),
            metadata={
                "holiday_name": created.name,
                "holiday_date": str(created.date),
            },
        )
    )

    return created


@router.put("/{holiday_id}", response_model=Holiday)
async def update_holiday(
    holiday_id: str,
    holiday_update: HolidayUpdate = Body(...),
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    before = await holiday_service.get_holiday_by_id(holiday_id)
    try:
        updated = await holiday_service.update_holiday(holiday_id, holiday_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Holiday not found")

    actor_name = current_user.full_name or current_user.username
    await log_service.create_log(
        ActivityLogCreate(
            action="holiday_updated",
            title="Holiday updated",
            description=f"{actor_name} updated a holiday: {updated.name}",
            actor_id=str(current_user.id),
            actor_name=actor_name,
            entity_type="holiday",
            entity_id=str(updated.id),
            metadata={
                "holiday_name": updated.name,
                "holiday_date": str(updated.date),
                "updated_fields": list(holiday_update.dict(exclude_unset=True).keys()),
                "previous": before.dict() if before else None,
            },
        )
    )

    return updated


@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    holiday_service: HolidayService = Depends(get_holiday_service),
    log_service: ActivityLogService = Depends(get_activity_log_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    existing = await holiday_service.get_holiday_by_id(holiday_id)
    deleted = await holiday_service.delete_holiday(holiday_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Holiday not found")

    actor_name = current_user.full_name or current_user.username
    if existing:
        await log_service.create_log(
            ActivityLogCreate(
                action="holiday_deleted",
                title="Holiday deleted",
                description=f"{actor_name} deleted a holiday: {existing.name}",
                actor_id=str(current_user.id),
                actor_name=actor_name,
                entity_type="holiday",
                entity_id=str(existing.id),
                metadata={
                    "holiday_name": existing.name,
                    "holiday_date": str(existing.date),
                },
            )
        )

    return {"success": True}
