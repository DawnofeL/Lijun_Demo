"""留痕查询。仅组长与管理员可见。

回传的是写入时就生成好的中文摘要，界面直接显示。
details 是逐栏变更，前端折叠起来，需要时才展开。
"""

import json

from fastapi import APIRouter, Depends

from core import db, deps

router = APIRouter(tags=["audit"])


@router.get("/audit")
def read_audit(
    limit: int = 200,
    user: deps.User = Depends(deps.require("supervisor", "admin")),
) -> dict:
    rows = db.query("SELECT * FROM audit_log ORDER BY created_at DESC, id DESC LIMIT ?",
                    (min(limit, 500),))
    for row in rows:
        raw = row.pop("details_json", None)
        row["details"] = json.loads(raw) if raw else []
        stamp = row["created_at"].replace("T", " ")
        row["date"], row["time"] = stamp.split(" ")[0], stamp.split(" ")[1]
    return {
        "note": "此表只追加，系統沒有提供修改或刪除的介面。任何一筆紀錄寫下之後就不會再變動。",
        "items": rows,
    }
