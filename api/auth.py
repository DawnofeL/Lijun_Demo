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


@router.get("/me")
def me(user: deps.User = Depends(deps.current_user)) -> dict:
    facility = db.query_one("SELECT name FROM facilities WHERE id = ?", (user.facility_id,))
    payload = user.as_dict()
    payload["facility_name"] = (facility or {}).get("name", "")
    return payload
