from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional, Tuple, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.leave import LeaveStatus
from app.models.leave_balance import LeaveBalanceItem, LeaveBalanceSummary, LeaveBalanceSummaryWithUser


DEFAULT_SICK_TOTAL = 12
DEFAULT_WFH_TOTAL = 5


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

    async def reset_entitlement_to_default(self, user_id: str, fy_start_year: Optional[int] = None) -> None:
        fy = fy_start_year
        if fy is None:
            fy, _, _ = get_financial_year_range()

        if not ObjectId.is_valid(str(user_id)):
            raise ValueError("Invalid user_id")

        query = {"user_id": ObjectId(str(user_id)), "fy_start_year": fy}
        update = {
            "$set": {
                "sick_total": DEFAULT_SICK_TOTAL,
                "wfh_total": DEFAULT_WFH_TOTAL,
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

    async def _fetch_approved_leaves(self, user_id: str, fy_start: date, fy_end: date) -> List[Dict]:
        if not ObjectId.is_valid(str(user_id)):
            return []

        # We query by overlap against the FY window (stored as datetime in DB)
        start_dt = datetime.combine(fy_start, datetime.min.time())
        end_dt = datetime.combine(fy_end, datetime.max.time())

        query = {
            "employee_id": ObjectId(str(user_id)),
            "status": LeaveStatus.APPROVED.value,
            "start_date": {"$lte": end_dt},
            "end_date": {"$gte": start_dt},
        }

        leaves: List[Dict] = []
        async for doc in self.leaves.find(query):
            leaves.append(doc)
        return leaves

    async def get_balance_for_user(self, user_id: str, today: Optional[date] = None) -> LeaveBalanceSummary:
        current_fy_start_year, _, _ = get_financial_year_range(today)
        entitlement = await self._get_or_create_entitlement(user_id, current_fy_start_year)

        fy_start_year = int(entitlement.get("fy_start_year", current_fy_start_year))
        _, fy_start, fy_end = get_financial_year_range(date(fy_start_year, 4, 1))

        sick_taken = 0
        wfh_taken = 0

        approved_leaves = await self._fetch_approved_leaves(user_id, fy_start, fy_end)

        for leave in approved_leaves:
            raw_start = leave.get("start_date")
            raw_end = leave.get("end_date")
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

            days = count_overlap_days(leave_start, leave_end, fy_start, fy_end)
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

        sick_item = LeaveBalanceItem(total=sick_total, taken=sick_taken, balance=max(sick_total - sick_taken, 0))
        wfh_item = LeaveBalanceItem(total=wfh_total, taken=wfh_taken, balance=max(wfh_total - wfh_taken, 0))

        reset_at = entitlement.get("updated_at")
        reset_at_str = None
        if isinstance(reset_at, datetime):
            reset_at_str = reset_at.isoformat()

        return LeaveBalanceSummary(
            fy_start_year=fy_start_year,
            fy_end_year=fy_start_year + 1,
            sick=sick_item,
            wfh=wfh_item,
            reset_at=reset_at_str,
        )

    async def get_balances_for_users(self, user_ids: List[str], today: Optional[date] = None) -> List[LeaveBalanceSummaryWithUser]:
        summaries: List[LeaveBalanceSummaryWithUser] = []
        for user_id in user_ids:
            summary = await self.get_balance_for_user(user_id, today=today)
            summaries.append(LeaveBalanceSummaryWithUser(user_id=str(user_id), **summary.model_dump()))
        return summaries


def get_leave_balance_service() -> LeaveBalanceService:
    return LeaveBalanceService(get_database())
