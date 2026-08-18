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
    """只按院舍限制，不限到个人。住客主档用这个。

    住客主档是院舍级共享的：同一间院舍的治疗师本来就要查得到彼此的住客，
    不然交更和补位就没法做。合规看板不同，见 resident_scope。
    """
    prefix = f"{table_alias}." if table_alias else ""
    if user.role == "admin":
        return "", []
    return f" AND {prefix}facility_id = ?", [user.facility_id]


def resident_scope(user: User, table_alias: str = "r") -> tuple[str, list]:
    """住客范围，职员限定到「本人负责的住客」。合规看板与今日工作台用这个。

    住客表上没有负责人栏位，负责关系是由工作节次建立的：
    谁被指派了这位住客的节次，谁就负责这位住客。所以这里走子查询，
    而不是在 residents 上加一个会跟排班脱节的冗余栏位。

    这一条和 facility_scope 的分工是刻意的，也是踩过的坑：
    合规看板问的是「谁没做到」，那是问责，问责必须落到人；
    住客主档问的是「这位住客是谁」，那是查档，查档限到人反而挡住正常协作。
    同一个 facility_scope 套在两种问题上，就会出现职员看到整间院舍的
    未达标名单——那既不是他的责任范围，也让权限演示当场失去说服力。
    """
    prefix = f"{table_alias}." if table_alias else ""
    if user.role == "staff":
        return (f" AND {prefix}id IN (SELECT resident_id FROM work_sessions"
                f" WHERE staff_id = ? AND is_deleted = 0)", [user.id])
    if user.role == "supervisor":
        return f" AND {prefix}facility_id = ?", [user.facility_id]
    return "", []


def audit_scope(user: User, table_alias: str = "") -> tuple[str, list]:
    """留痕范围。组长只看本院舍，管理员看全部。

    facility_id 为空的是系统层级动作，不属于任何一间院舍，一律可见。
    """
    prefix = f"{table_alias}." if table_alias else ""
    if user.role == "admin":
        return "", []
    return (f" AND ({prefix}facility_id = ? OR {prefix}facility_id IS NULL)",
            [user.facility_id])
