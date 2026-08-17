"""全篇枢纽：身份、角色守卫、资料范围。

范围过滤只写在这一个地方。权限漏洞几乎都出在「几十个接口里漏写了一个判断」，
所有查询共用同一段条件，就没有漏写的余地。
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from core import db, security

ROLE_LABELS = {
    "staff": "職員",
    "supervisor": "組長",
    "admin": "管理員",
}

SCOPE_LABELS = {
    "staff": "你正在查看：指派給你本人的節次",
    "supervisor": "你正在查看：本院舍全部節次",
    "admin": "你正在查看：全部院舍",
}


@dataclass
class User:
    id: int
    staff_no: str
    username: str
    display_name: str
    position: str
    role: str
    facility_id: str

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def scope_label(self) -> str:
        return SCOPE_LABELS.get(self.role, "")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "staff_no": self.staff_no,
            "username": self.username,
            "display_name": self.display_name,
            "position": self.position,
            "role": self.role,
            "role_label": self.role_label,
            "facility_id": self.facility_id,
            "scope_label": self.scope_label,
        }


def current_user(authorization: str = Header(default="")) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "尚未登入")
    user_id = security.read_token(authorization[7:])
    if user_id is None:
        raise HTTPException(401, "登入已失效，請重新登入")
    row = db.query_one(
        "SELECT id, staff_no, username, display_name, position, role, facility_id"
        " FROM staff WHERE id = ? AND is_deleted = 0",
        (user_id,),
    )
    if not row:
        raise HTTPException(401, "帳號不存在")
    return User(**row)


def require(*roles: str):
    """角色守卫。接口签名上加一行即可完成鉴权。"""
    allowed = set(roles)

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            labels = "、".join(ROLE_LABELS.get(r, r) for r in roles)
            raise HTTPException(403, f"此功能僅限：{labels}")
        return user

    return dependency


def scope_filter(user: User, table_alias: str = "") -> tuple[str, list]:
    """回传一段 SQL 条件和参数。

    职员限定到本人，组长限定到本院舍，管理员不加限制。
    table_alias 用于联表查询时指明字段属于哪张表。
    """
    prefix = f"{table_alias}." if table_alias else ""
    if user.role == "staff":
        return f" AND {prefix}staff_id = ?", [user.id]
    if user.role == "supervisor":
        return f" AND {prefix}facility_id = ?", [user.facility_id]
    return "", []


def facility_scope(user: User, table_alias: str = "") -> tuple[str, list]:
    """只按院舍限制，不限到个人。住客主档、合规看板用这个。"""
    prefix = f"{table_alias}." if table_alias else ""
    if user.role == "admin":
        return "", []
    return f" AND {prefix}facility_id = ?", [user.facility_id]
