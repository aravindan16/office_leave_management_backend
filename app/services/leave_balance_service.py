from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional, Tuple, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.leave import LeaveStatus
from app.models.leave_balance import LeaveBalanceItem, LeaveBalanceSummary, LeaveBalanceSummaryWithUser


DEFAULT_SICK_TOTAL = 12
DEFAULT_WFH_TOTAL = 12


def get_financial_year_range(today: Optional[date] = None) -> Tuple[int, date, date]:
    if today is None:
        today = datetime.utcnow().date()

    if today.month >= 4:
        fy_start_year = today.year
    else:
        fy_start_year = today.year - 1

    start = date(fy_start_year, 4, 1)
    end = date(fy_start_year + 1, 3, 31)
    return fy_start_year, start, end


def count_overlap_days(start: date, end: date, range_start: date, range_end: date) -> int:
    effective_start = max(start, range_start)
    effective_end = min(end, range_end)
    if effective_end < effective_start:
        return 0
    return (effective_end - effective_start).days + 1


def count_overlap_working_days(start: date, end: date, range_start: date, range_end: date) -> int:
    effective_start = max(start, range_start)
    effective_end = min(end, range_end)
    if effective_end < effective_start:
        return 0

    from datetime import timedelta

    count = 0
    d = effective_start
    while d <= effective_end:
        if d.weekday() < 5:
            count += 1
        d = d + timedelta(days=1)
    return count


def get_counted_days(leave: Dict, leave_start: date, leave_end: date, fy_start: date, fy_end: date) -> float:
    overlap_days = count_overlap_days(leave_start, leave_end, fy_start, fy_end)
    overlap_working_days = count_overlap_working_days(leave_start, leave_end, fy_start, fy_end)
    if overlap_days <= 0:
        return 0

    duration = leave.get("duration_days")
    try:
        duration_value = float(duration)
    except (TypeError, ValueError):
        duration_value = 0

    if duration_value > 0:
        full_range_days = max((leave_end - leave_start).days + 1, 1)
        if full_range_days == 1:
            return duration_value
        return min(float(overlap_working_days), duration_value)

    return float(overlap_working_days)


class LeaveBalanceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.leaves = db.leaves
        self.entitlements = db.leave_entitlements

    async def _get_or_create_entitlement(self, user_id: str, fy_start_year: int) -> Dict:
        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": fy_start_year}
        existing = await self.entitlements.find_one(query)
        if existing:
            return existing

        # Do not auto-create a new entitlement every FY. If the admin hasn't reset yet,
        # keep using the latest existing entitlement.
        latest = await self.entitlements.find_one(
            {"user_id": ObjectId(str(user_id))},
            sort=[("fy_start_year", -1)],
        )
        if latest:
            return latest

        doc = {
            **query,
            "sick_total": DEFAULT_SICK_TOTAL,
            "wfh_total": DEFAULT_WFH_TOTAL,
            "updated_at": datetime.utcnow(),
        }
        await self.entitlements.insert_one(doc)
        return doc

    async def _ensure_entitlement_for_financial_year(self, user_id: str, fy_start_year: int) -> Dict:
        """
        Ensure an entitlement document exists for the requested FY.
        New FY entries always reset sick leave to default (12), while preserving
        the latest configured WFH total.
        """
        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": int(fy_start_year)}
        existing = await self.entitlements.find_one(query)
        if existing:
            return existing

        latest = await self.entitlements.find_one(
            {"user_id": ObjectId(str(user_id))},
            sort=[("fy_start_year", -1)],
        )
        wfh_total = int(latest.get("wfh_total", DEFAULT_WFH_TOTAL)) if latest else DEFAULT_WFH_TOTAL
        wfh_total = max(wfh_total, DEFAULT_WFH_TOTAL)

        doc = {
            **query,
            "sick_total": DEFAULT_SICK_TOTAL,
            "wfh_total": wfh_total,
            "updated_at": datetime.utcnow(),
        }
        await self.entitlements.insert_one(doc)
        return doc

    async def _get_entitlement_for_fy(self, user_id: str, fy_start_year: int) -> Dict:
        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": int(fy_start_year)}
        existing = await self.entitlements.find_one(query)
        if existing:
            return existing

        return {
            **query,
            "sick_total": DEFAULT_SICK_TOTAL,
            "wfh_total": DEFAULT_WFH_TOTAL,
            "updated_at": None,
        }

    async def reset_entitlement_to_default(
        self, 
        user_id: str, 
        sick_total: Optional[int] = None,
        wfh_total: Optional[int] = None,
        fy_start_year: Optional[int] = None
    ) -> None:
        fy = fy_start_year
        if fy is None:
            fy, _, _ = get_financial_year_range()

        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        s_total = sick_total if sick_total is not None else DEFAULT_SICK_TOTAL
        w_total = wfh_total if wfh_total is not None else DEFAULT_WFH_TOTAL

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": fy}
        update = {
            "$set": {
                "sick_total": s_total,
                "wfh_total": w_total,
                "updated_at": datetime.utcnow(),
            }
        }
        await self.entitlements.update_one(query, update, upsert=True)


    async def set_entitlement_totals(self, user_id: str, sick_total: int, wfh_total: int, fy_start_year: Optional[int] = None) -> None:
        fy = fy_start_year
        if fy is None:
            fy, _, _ = get_financial_year_range()

        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": fy}
        update = {
            "$set": {
                "sick_total": int(sick_total),
                "wfh_total": int(wfh_total),
                "updated_at": datetime.utcnow(),
            }
        }
        await self.entitlements.update_one(query, update, upsert=True)

    async def _fetch_counted_leaves(
        self,
        user_id: str,
        fy_start: date,
        fy_end: date,
        include_pending: bool = True,
    ) -> List[Dict]:
        if not ObjectId.is_valid(str(user_id)):
            return []

        # We query by overlap against the FY window (stored as datetime in DB)
        start_dt = datetime.combine(fy_start, datetime.min.time())
        end_dt = datetime.combine(fy_end, datetime.max.time())

        statuses = [LeaveStatus.APPROVED.value]
        if include_pending:
            statuses.append(LeaveStatus.PENDING.value)

        query = {
            "employee_id": ObjectId(str(user_id)),
            "status": {"$in": statuses},
            "start_date": {"$lte": end_dt},
            "end_date": {"$gte": start_dt},
        }

        leaves: List[Dict] = []
        async for doc in self.leaves.find(query):
            leaves.append(doc)
        return leaves

    async def get_balance_for_user(
        self,
        user_id: str,
        today: Optional[date] = None,
        fy_start_year: Optional[int] = None,
        include_pending: bool = True,
    ) -> LeaveBalanceSummary:
        current_fy_start_year, _, _ = get_financial_year_range(today)

        if fy_start_year is None:
            entitlement = await self._ensure_entitlement_for_financial_year(user_id, current_fy_start_year)
            resolved_fy_start_year = int(entitlement.get("fy_start_year", current_fy_start_year))
        else:
            entitlement = await self._get_entitlement_for_fy(user_id, int(fy_start_year))
            resolved_fy_start_year = int(fy_start_year)

        _, fy_start, fy_end = get_financial_year_range(date(resolved_fy_start_year, 4, 1))

        sick_taken = 0.0
        wfh_taken = 0.0

        counted_leaves = await self._fetch_counted_leaves(
            user_id,
            fy_start,
            fy_end,
            include_pending=include_pending,
        )
        reset_at = entitlement.get("updated_at")

        for leave in counted_leaves:
            raw_start = leave.get("start_date")
            raw_end = leave.get("end_date")

            if reset_at and isinstance(reset_at, datetime):
                # If the leave was created before the most recent reset, 
                # we ignore it to ensure the balance stays at the full allowance.
                created_at = leave.get("created_at")
                if isinstance(created_at, datetime) and created_at < reset_at:
                    continue



            if isinstance(raw_start, datetime):

                leave_start = raw_start.date()
            elif isinstance(raw_start, date):
                leave_start = raw_start
            else:
                continue

            if isinstance(raw_end, datetime):
                leave_end = raw_end.date()
            elif isinstance(raw_end, date):
                leave_end = raw_end
            else:
                continue

            days = get_counted_days(leave, leave_start, leave_end, fy_start, fy_end)
            if days <= 0:
                continue

            request_type = str(leave.get("request_type") or "").lower()
            leave_type = str(leave.get("leave_type") or "").lower()

            if request_type == "wfh":
                wfh_taken += days
            elif request_type == "leave" and leave_type == "sick":
                sick_taken += days

        sick_total = int(entitlement.get("sick_total", DEFAULT_SICK_TOTAL))
        wfh_total = int(entitlement.get("wfh_total", DEFAULT_WFH_TOTAL))
        wfh_total = max(wfh_total, DEFAULT_WFH_TOTAL)

        sick_item = LeaveBalanceItem(total=sick_total, taken=sick_taken, balance=max(sick_total - sick_taken, 0))
        wfh_item = LeaveBalanceItem(total=wfh_total, taken=wfh_taken, balance=max(wfh_total - wfh_taken, 0))

        reset_at = entitlement.get("updated_at")
        reset_at_str = None
        if isinstance(reset_at, datetime):
            reset_at_str = reset_at.isoformat()

        return LeaveBalanceSummary(
            fy_start_year=resolved_fy_start_year,
            fy_end_year=resolved_fy_start_year + 1,
            sick=sick_item,
            wfh=wfh_item,
            reset_at=reset_at_str,
        )

    async def reset_sick_leave_for_all_users(self, user_ids: List[str], fy_start_year: int) -> None:
        for user_id in user_ids:
            if not ObjectId.is_valid(str(user_id)):
                continue

            latest = await self.entitlements.find_one(
                {"user_id": ObjectId(str(user_id))},
                sort=[("fy_start_year", -1)],
            )
            wfh_total = int(latest.get("wfh_total", DEFAULT_WFH_TOTAL)) if latest else DEFAULT_WFH_TOTAL
            wfh_total = max(wfh_total, DEFAULT_WFH_TOTAL)

            await self.reset_entitlement_to_default(
                user_id=user_id,
                sick_total=DEFAULT_SICK_TOTAL,
                wfh_total=wfh_total,
                fy_start_year=int(fy_start_year),
            )

    async def get_balances_for_users(
        self,
        user_ids: List[str],
        today: Optional[date] = None,
        fy_start_year: Optional[int] = None,
        include_pending: bool = True,
    ) -> List[LeaveBalanceSummaryWithUser]:
        summaries: List[LeaveBalanceSummaryWithUser] = []
        for user_id in user_ids:
            summary = await self.get_balance_for_user(
                user_id,
                today=today,
                fy_start_year=fy_start_year,
                include_pending=include_pending,
            )
            summaries.append(LeaveBalanceSummaryWithUser(user_id=str(user_id), **summary.model_dump()))
        return summaries


def get_leave_balance_service() -> LeaveBalanceService:
    return LeaveBalanceService(get_database())
