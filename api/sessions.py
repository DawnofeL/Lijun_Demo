"""工作计划。同一个接口三种角色看到的范围不同，差异来自 deps.scope_filter。

回传体带上 scope_label，前端据此显示「你正在查看：本院舍全部節次」这行字。
现场切换帐号演示时，这行字就是权限隔离最直观的证明。
"""

from datetime import date

from fastapi import APIRouter, Depends

from core import db, deps
from domain import rules

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
def list_sessions(
    session_date: str | None = None,
    user: deps.User = Depends(deps.current_user),
) -> dict:
    target_date = session_date or date.today().isoformat()
    where, args = deps.scope_filter(user, "s")

    rows = db.query(
        "SELECT s.id, s.session_date, s.start_time, s.end_time, s.service_type,"
        " s.service_track, s.status, r.name AS resident_name, r.bed_no,"
        " r.funding_type, u.display_name AS staff_name, f.name AS facility_name"
        " FROM work_sessions s"
        " JOIN residents r ON r.id = s.resident_id"
        " JOIN staff u ON u.id = s.staff_id"
        " JOIN facilities f ON f.id = s.facility_id"
        " WHERE s.is_deleted = 0 AND s.session_date = ?" + where +
        " ORDER BY s.start_time, f.name",
        [target_date] + args,
    )
    for row in rows:
        row["badge"] = rules.session_badge(row["status"])

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "date": target_date,
        "scope": user.role,
        "scope_label": user.scope_label,
        "summary": counts,
        "items": rows,
    }


@router.get("/sessions/dates")
def available_dates(user: deps.User = Depends(deps.current_user)) -> dict:
    """回传有资料的日期范围，前端日期选择器用它设定上下限。"""
    where, args = deps.scope_filter(user, "s")
    row = db.query_one(
        "SELECT MIN(s.session_date) AS first_date, MAX(s.session_date) AS last_date"
        " FROM work_sessions s WHERE s.is_deleted = 0" + where,
        args,
    )
    return {
        "first_date": (row or {}).get("first_date"),
        "last_date": (row or {}).get("last_date"),
        "today": date.today().isoformat(),
    }
