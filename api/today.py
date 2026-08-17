"""今日工作台。系統的起點。

進來先看到今天要做什麼，而不是先看到一份功能目錄。
資料全部來自現有的表，這裡只做聚合，不新增任何資料結構。
"""

from datetime import date

from fastapi import APIRouter, Depends

from core import db, deps
from domain import rules

router = APIRouter(tags=["today"])


@router.get("/today")
def today(user: deps.User = Depends(deps.current_user)) -> dict:
    day = date.today().isoformat()
    where, args = deps.scope_filter(user, "s")
    fac_where, fac_args = deps.facility_scope(user, "r")

    # 今日節次，按時間排。這是時間線的主體。
    sessions = db.query(
        "SELECT s.id, s.start_time, s.end_time, s.service_type, s.status,"
        " r.name AS resident_name, r.bed_no, r.funding_type,"
        " u.display_name AS staff_name, f.name AS facility_name"
        " FROM work_sessions s"
        " JOIN residents r ON r.id = s.resident_id"
        " JOIN staff u ON u.id = s.staff_id"
        " JOIN facilities f ON f.id = s.facility_id"
        " WHERE s.is_deleted = 0 AND s.session_date = ?" + where +
        " ORDER BY s.start_time",
        [day] + args,
    )
    # 「進行中」只能有一節：時間落在區間內的那一節；
    # 都不落在區間內時，取下一節將要開始的。全部標亮等於全部沒標。
    from datetime import datetime
    clock = datetime.now().strftime("%H:%M")
    current_id = None
    for row in sessions:
        row["badge"] = rules.session_badge(row["status"])
        row["is_now"] = False
        if row["status"] in ("已接收", "待接收") and row["start_time"] <= clock <= row["end_time"]:
            current_id = current_id or row["id"]
    if current_id is None:
        upcoming = [r for r in sessions
                    if r["status"] in ("已接收", "待接收") and r["start_time"] >= clock]
        current_id = upcoming[0]["id"] if upcoming else None
    for row in sessions:
        row["is_now"] = row["id"] == current_id

    counts: dict[str, int] = {}
    for row in sessions:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    # 需要處理的三件事。側欄上的紅點就是這三個數字。
    gaps = db.query_one(
        "SELECT COUNT(*) AS n FROM work_sessions s"
        " WHERE s.is_deleted = 0 AND s.status = '已完成'"
        " AND NOT EXISTS (SELECT 1 FROM form_submissions x"
        "                 WHERE x.session_id = s.id AND x.is_deleted = 0)" + where,
        args,
    )["n"]

    residents = db.query(
        "SELECT r.id, r.last_assessed, r.weekly_target,"
        " (SELECT COUNT(*) FROM work_sessions s WHERE s.resident_id = r.id"
        "  AND s.is_deleted = 0 AND s.status = '已完成'"
        "  AND s.session_date BETWEEN ? AND ?) AS completed"
        " FROM residents r WHERE r.is_deleted = 0" + fac_where,
        [rules.pick_week()["from"], rules.pick_week()["to"]] + fac_args,
    )

    overdue = due_soon = behind = 0
    for row in residents:
        level = rules.assessment_status(row["last_assessed"])["level"]
        if level in ("overdue", "never"):
            overdue += 1
        elif level == "due_soon":
            due_soon += 1
        if rules.target_status(row["completed"], row["weekly_target"])["level"] == "behind":
            behind += 1

    recent = db.query(
        "SELECT actor_name, actor_role, summary, created_at FROM audit_log"
        " ORDER BY created_at DESC, id DESC LIMIT 4"
    ) if user.role in ("supervisor", "admin") else []

    return {
        "date": day,
        "scope_label": user.scope_label,
        "facility": db.query_one("SELECT name FROM facilities WHERE id = ?",
                                 (user.facility_id,))["name"],
        "summary": {
            "total": len(sessions),
            "done": counts.get("已完成", 0),
            "pending": counts.get("待接收", 0) + counts.get("已接收", 0),
            "absent": counts.get("未能出席", 0),
        },
        "timeline": sessions[:12],
        "attention": {"gaps": gaps, "overdue": overdue,
                      "due_soon": due_soon, "behind": behind},
        "recent": recent,
    }
