from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from io import BytesIO
from datetime import datetime
from typing import List

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
):
    holidays = await holiday_service.get_all_holidays()

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
        # Start near top-left margin
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
        contents_obj = b"<< /Length " + str(len(text_stream)).encode("ascii") + b" >>\nstream\n" + text_stream + b"endstream"

        # Objects
        # 1: Catalog, 2: Pages, 3: Page, 4: Font, 5: Contents
        objs: List[bytes] = []
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
        objs.append(font_obj)
        objs.append(contents_obj)

        # Write file with xref
        out = bytearray()
        out += header
        offsets = [0]  # xref entry 0
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

    def fmt_date(value: str) -> str:
        if not value:
            return ""
        try:
            d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return d.date().strftime("%d/%m/%Y")
        except Exception:
            try:
                d2 = datetime.strptime(str(value)[:10], "%Y-%m-%d")
                return d2.date().strftime("%d/%m/%Y")
            except Exception:
                return str(value)

    now = datetime.utcnow()
    fy_start_year = now.year if now.month >= 4 else now.year - 1
    fy_label = f"Financial Year: 01/04/{fy_start_year} to 31/03/{fy_start_year + 1}"
    lines: List[str] = []
    lines.append("Holiday List")
    lines.append(fy_label)
    lines.append("")
    lines.append("#   Date        Name")
    lines.append("----------------------------------------------")
    if not holidays:
        lines.append("No holidays found")
    else:
        for idx, h in enumerate(holidays, start=1):
            date_label = fmt_date(getattr(h, "date", ""))
            name = str(getattr(h, "name", "") or "")
            lines.append(f"{idx:>2}  {date_label:<10}  {name}")

    pdf_bytes = _build_minimal_pdf(lines)
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
