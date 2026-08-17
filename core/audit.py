"""留痕写入。只追加，没有更新和删除接口。

纸本纪录有个隐性优点，涂改的痕迹擦不掉。系统若不留痕，
在监管与投诉面前反而比纸更弱，所以这张表是第一优先。

写入时就把「谁做了什么」写成一句中文存进 summary。
界面直接显示那句话，不让使用者去读 JSON。
需要细节时看 details，那是一组「栏位、原本、改为」的三列资料，
栏位名同样是中文，界面上永远不出现花括号。
"""

import json
from datetime import datetime
from typing import Any

from core import db


def change(field: str, before: Any = None, after: Any = None) -> dict:
    """一条逐栏变更。栏位名用中文，值转成人看得懂的字串。"""
    def render(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (list, tuple)):
            return "、".join(str(v) for v in value)
        if isinstance(value, dict):
            return "、".join(f"{k}：{v}" for k, v in value.items())
        return str(value)

    return {"field": field, "before": render(before), "after": render(after)}


def write(
    actor,
    action: str,
    summary: str,
    entity: str,
    entity_id: str | int,
    details: list[dict] | None = None,
) -> None:
    """actor 是 deps.User，也接受 None（系统操作）。

    action 是短标签（登入、提交服務表單……），给界面做徽章用。
    summary 是完整的一句话，是使用者真正会读的那行。
    """
    db.execute(
        "INSERT INTO audit_log(actor_id, actor_name, actor_role, action, summary,"
        " entity, entity_id, details_json, facility_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            getattr(actor, "id", None),
            getattr(actor, "display_name", "系統"),
            getattr(actor, "role_label", "系統"),
            action,
            summary,
            entity,
            str(entity_id),
            json.dumps(details, ensure_ascii=False) if details else None,
            getattr(actor, "facility_id", None),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
