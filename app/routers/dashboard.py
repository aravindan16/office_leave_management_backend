from datetime import date, datetime, time
from typing import List

from fastapi import APIRouter, Depends

from app.models.dashboard import (
    DashboardBirthdayItem,
    DashboardEmployee,
    DashboardSummary,
    DashboardUpcomingItem,
)
from app.models.user import UserInDB
from app.routers.auth import get_current_active_user
from app.services.leave_service import LeaveService, get_leave_service
from app.services.user_service import UserService, get_user_service


router = APIRouter()


def _to_iso(d) -> str:
    if d is None:
        return ""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, datetime):
        return d.date().isoformat()
    return str(d)


def _to_employee(u) -> DashboardEmployee:
    return DashboardEmployee(
        id=str(getattr(u, "id", "")),
        full_name=getattr(u, "full_name", "") or "",
        username=getattr(u, "username", "") or "",
        email=getattr(u, "email", "") or "",
        position=getattr(u, "position", "") or "",
        profile_image=getattr(u, "profile_image", "") or "",
        date_of_birth=_to_iso(getattr(u, "date_of_birth", None)) if getattr(u, "date_of_birth", None) else None,
    )


def _add_months(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = d.day

    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: UserInDB = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
    leave_service: LeaveService = Depends(get_leave_service),
):
    users = await user_service.get_all_users()
    active_users = list(users or [])
    employees = [u for u in (active_users or []) if not getattr(u, "is_admin", False) and not getattr(u, "is_manager", False)]

    today = date.today()
    next_three_month_cutoff = _add_months(today, 3)

    birthdays: List[DashboardBirthdayItem] = []
    for u in employees:
        dob = getattr(u, "date_of_birth", None)
        if not dob:
            continue
        if isinstance(dob, datetime):
            dob = dob.date()
        if not isinstance(dob, date):
            continue

        try:
            next_bd = date(today.year, dob.month, dob.day)
        except Exception:
            continue

        if next_bd < today:
            try:
                next_bd = date(today.year + 1, dob.month, dob.day)
            except Exception:
                continue

        if next_bd >= next_three_month_cutoff:
            continue

        birthdays.append(
            DashboardBirthdayItem(
                user=_to_employee(u),
                next_birthday=_to_iso(next_bd),
            )
        )

    birthdays.sort(key=lambda x: x.next_birthday)

    start_dt = datetime.combine(today, time.min)

    # Leaves are stored as datetimes in Mongo, but normalized to dates on output.
    cursor = leave_service.collection.find(
        {
            "status": "approved",
            "end_date": {"$gte": start_dt},
        }
    )

    upcoming: List[DashboardUpcomingItem] = []
    async for leave_data in cursor:
        leave_data["id"] = str(leave_data.pop("_id"))
        employee_id = str(leave_data.get("employee_id"))
        leave_data["employee_id"] = employee_id
        if leave_data.get("manager_id") is not None:
            leave_data["manager_id"] = str(leave_data["manager_id"])

        start_raw = leave_data.get("start_date")
        end_raw = leave_data.get("end_date")
        start_iso = _to_iso(start_raw)[:10]
        end_iso = _to_iso(end_raw)[:10]

        emp = next((e for e in employees if str(getattr(e, "id", "")) == employee_id), None)
        if not emp:
            continue

        upcoming.append(
            DashboardUpcomingItem(
                id=str(leave_data.get("id", "")),
                request_type=str(leave_data.get("request_type", "leave")),
                leave_type=str(leave_data.get("leave_type", "")),
                start_date=start_iso,
                end_date=end_iso,
                employee=_to_employee(emp),
            )
        )

    upcoming.sort(key=lambda x: (x.start_date or "", x.end_date or ""))

    return DashboardSummary(
        birthdays_this_month=birthdays[:12],
        upcoming_approved=upcoming[:12],
    )
