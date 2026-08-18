"""留痕查询。仅组长与管理员可见。

回传的是写入时就生成好的中文摘要，界面直接显示。
details 是逐栏变更，前端折叠起来，需要时才展开。
"""

import json

from fastapi import APIRouter, Depends, Query

from core import db, deps

router = APIRouter(tags=["audit"])


@router.get("/audit")
def read_audit(
    # 上下界都要卡。原本寫 min(limit, 500)，負數會漏過去，
    # 而 SQLite 的 LIMIT -1 意思是「不限制」——?limit=-1 就能把整張表拖出來。
    # 現在只有一百多筆看不出問題，留痕表長到百萬級時這是一發即中的。
    limit: int = Query(200, ge=1, le=500),
    user: deps.User = Depends(deps.require("supervisor", "admin")),
) -> dict:
    # 組長只看本院舍。這裡漏掉範圍限制的話，正好是在「證明權限隔離」
    # 的那一頁上把隔離漏掉，切帳號演示時第一個被抓到的就是它。
    where, args = deps.audit_scope(user)
    rows = db.query(
        "SELECT * FROM audit_log WHERE 1 = 1" + where +
        " ORDER BY created_at DESC, id DESC LIMIT ?",
        args + [limit],
    )
    for row in rows:
        raw = row.pop("details_json", None)
        row["details"] = json.loads(raw) if raw else []
        stamp = row["created_at"].replace("T", " ")
        row["date"], row["time"] = stamp.split(" ")[0], stamp.split(" ")[1]
    return {
        "note": "此表只追加，系統沒有提供修改或刪除的介面。任何一筆紀錄寫下之後就不會再變動。",
        "items": rows,
    }
