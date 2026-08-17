"""合规看板。所有判断都在 domain.rules，这里只负责取数与拼装。"""

from fastapi import APIRouter, Depends

from core import db, deps
from domain import rules

router = APIRouter(tags=["compliance"])


@router.get("/compliance/targets")
def weekly_targets(
    week: str = "auto",
    user: deps.User = Depends(deps.current_user),
) -> dict:
    """资助目标达成率。week 可为 auto / current / last。"""
    period = rules.pick_week(week)
    where, args = deps.facility_scope(user, "r")

    rows = db.query(
        "SELECT r.id, r.bed_no, r.name, r.funding_type, r.service_track, r.weekly_target,"
        " f.name AS facility_name,"
        " (SELECT COUNT(*) FROM work_sessions s"
        "  WHERE s.resident_id = r.id AND s.is_deleted = 0 AND s.status = '已完成'"
        "  AND s.session_date BETWEEN ? AND ?) AS completed"
        " FROM residents r JOIN facilities f ON f.id = r.facility_id"
        " WHERE r.is_deleted = 0" + where +
        " ORDER BY r.facility_id, r.bed_no",
        [period["from"], period["to"]] + args,
    )

    items = []
    tally = {"met": 0, "at_risk": 0, "behind": 0}
    for row in rows:
        status = rules.target_status(row["completed"], row["weekly_target"])
        tally[status["level"]] += 1
        items.append({**row, **status})

    items.sort(key=lambda x: (x["rate"], x["bed_no"]))
    return {
        "week": period,
        "scope_label": user.scope_label,
        "summary": tally,
        "items": items,
    }


@router.get("/compliance/assessments")
def assessment_due(user: deps.User = Depends(deps.current_user)) -> dict:
    """180 天评估周期追踪。逾期与从未评估排最前。"""
    where, args = deps.facility_scope(user, "r")
    rows = db.query(
        "SELECT r.id, r.bed_no, r.name, r.funding_type, r.last_assessed,"
        " f.name AS facility_name"
        " FROM residents r JOIN facilities f ON f.id = r.facility_id"
        " WHERE r.is_deleted = 0" + where,
        args,
    )

    items = []
    tally = {"overdue": 0, "due_soon": 0, "normal": 0, "never": 0}
    for row in rows:
        status = rules.assessment_status(row["last_assessed"])
        tally[status["level"]] += 1
        items.append({**row, **status})

    order = {"never": 0, "overdue": 1, "due_soon": 2, "normal": 3}
    items.sort(key=lambda x: (order[x["level"]], x["days_left"] if x["days_left"] is not None else -999))

    return {
        "cycle_days": 180,
        "scope_label": user.scope_label,
        "summary": tally,
        "items": items,
    }


@router.get("/compliance/gaps")
def form_gaps(user: deps.User = Depends(deps.current_user)) -> dict:
    """已完成但未填表的节次。这是纸本转系统时最常见的缺口。"""
    where, args = deps.scope_filter(user, "s")
    rows = db.query(
        "SELECT s.id, s.session_date, s.start_time, s.service_type,"
        " r.bed_no, r.name AS resident_name, u.display_name AS staff_name,"
        " f.name AS facility_name"
        " FROM work_sessions s"
        " JOIN residents r ON r.id = s.resident_id"
        " JOIN staff u ON u.id = s.staff_id"
        " JOIN facilities f ON f.id = s.facility_id"
        " WHERE s.is_deleted = 0 AND s.status = '已完成'"
        " AND NOT EXISTS (SELECT 1 FROM form_submissions x"
        "                 WHERE x.session_id = s.id AND x.is_deleted = 0)" + where +
        " ORDER BY s.session_date DESC, s.start_time LIMIT 200",
        args,
    )
    total = db.query_one(
        "SELECT COUNT(*) AS n FROM work_sessions s"
        " WHERE s.is_deleted = 0 AND s.status = '已完成'"
        " AND NOT EXISTS (SELECT 1 FROM form_submissions x"
        "                 WHERE x.session_id = s.id AND x.is_deleted = 0)" + where,
        args,
    )
    return {"scope_label": user.scope_label, "total": total["n"], "items": rows}
