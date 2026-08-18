"""登入与当前使用者。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, db, deps, security

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn) -> dict:
    row = db.query_one(
        "SELECT * FROM staff WHERE username = ? AND is_deleted = 0", (body.username,)
    )
    if not row or not security.verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "帳號或密碼不正確")

    user = deps.User(**{k: row[k] for k in (
        "id", "staff_no", "username", "display_name", "position", "role", "facility_id")})
    audit.write(user, "登入", "登入系統", "staff", user.id)

    facility = db.query_one("SELECT name FROM facilities WHERE id = ?", (user.facility_id,))
    payload = user.as_dict()
    payload["facility_name"] = (facility or {}).get("name", "")
    return {"token": security.issue_token(user.id), "user": payload}


@router.get("/scope")
def scope(user: deps.User = Depends(deps.current_user)) -> dict:
    """当前身份的视野量化。

    权限的本质是「看不到的东西」，而看不到的东西没法展示——
    「职员少了一个选单项」是消极证据，观众感受不到没发生的事。
    所以这里把被挡掉的量算出来，让消极证据变成积极证据：
    不列出你看不到的住客是谁，只告诉你「另有 80 位不在你的范围内」。

    回传的分母是全系统的聚合计数，不含任何住客身份、床号或状态，
    泄露的只有「还剩多少」这一个数字。员工本来就知道公司有几间院舍。

    两个范围刻意分开回传，因为系统里它们本来就是两件事：
    responsible 是 resident_scope，问责用，合规看板与今日工作台按它统计；
    readable   是 facility_scope，查档用，住客主档按它列。
    职员对 12 位负责，但查得到本院舍全部 30 位——这个差别不是 bug，
    是「问责落到人、查档落到院舍」的设计，被问到时正好是个好答案。
    """
    total = db.query_one(
        "SELECT COUNT(*) AS n FROM residents WHERE is_deleted = 0")["n"]
    total_facilities = db.query_one("SELECT COUNT(*) AS n FROM facilities")["n"]

    own_where, own_args = deps.resident_scope(user, "r")
    responsible = db.query_one(
        "SELECT COUNT(*) AS n FROM residents r WHERE r.is_deleted = 0" + own_where,
        own_args)["n"]

    read_where, read_args = deps.facility_scope(user, "r")
    readable = db.query_one(
        "SELECT COUNT(*) AS n FROM residents r WHERE r.is_deleted = 0" + read_where,
        read_args)["n"]
    facilities = db.query_one(
        "SELECT COUNT(DISTINCT r.facility_id) AS n FROM residents r"
        " WHERE r.is_deleted = 0" + read_where, read_args)["n"]

    return {
        "role": user.role,
        "role_label": user.role_label,
        "scope_label": user.scope_label,
        "responsible": responsible,
        "readable": readable,
        "residents_total": total,
        "facilities": facilities,
        "facilities_total": total_facilities,
        "hidden_residents": max(total - responsible, 0),
        "hidden_facilities": max(total_facilities - facilities, 0),
    }


@router.get("/me")
def me(user: deps.User = Depends(deps.current_user)) -> dict:
    facility = db.query_one("SELECT name FROM facilities WHERE id = ?", (user.facility_id,))
    payload = user.as_dict()
    payload["facility_name"] = (facility or {}).get("name", "")
    return payload
