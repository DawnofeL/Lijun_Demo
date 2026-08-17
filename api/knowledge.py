"""知识库问答接口。转调 knowledge 层，并写一条留痕记录谁问了什么。"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from core import audit, deps
from knowledge import answer as answer_module
from knowledge import assistant, ingest, llm

router = APIRouter(tags=["knowledge"])

SUGGESTIONS = [
    "住客跌倒之後的處理流程是什麼",
    "評估周期是多久，逾期怎麼辦",
    "已提交的紀錄可以直接修改嗎",
    "批次匯入住客名單有什麼限制",
]


class AskIn(BaseModel):
    question: str


@router.get("/knowledge/status")
def status(user: deps.User = Depends(deps.current_user)) -> dict:
    info = ingest.stats()
    return {
        **info,
        "llm_available": llm.available(),
        "demo_mode": config.DEMO_MODE,
        "suggestions": SUGGESTIONS,
        "note": "答案僅依據已入庫的文件，每句標註出處。庫中沒有依據時會明確回覆找不到。",
    }


@router.post("/knowledge/ask")
async def ask(body: AskIn, user: deps.User = Depends(deps.current_user)) -> dict:
    question = body.question.strip()
    if not question:
        return {"question": "", "answer": "請輸入問題。", "passages": [], "mode": "empty"}

    result = await answer_module.answer(question)
    hits = len(result["passages"])
    short = question if len(question) <= 22 else question[:22] + "…"
    summary = (f"查詢知識庫「{short}」，命中 {hits} 段規範"
               if hits else f"查詢知識庫「{short}」，庫中沒有找到依據")
    audit.write(
        user, "知識庫查詢", summary, "knowledge", "-",
        details=[
            audit.change("提問內容", after=question),
            audit.change("命中段落數", after=hits),
            audit.change("引用出處", after=[p["citation"] for p in result["passages"]] or "無"),
        ],
    )
    return result


# ---------------------------------------------------------------------------
# 智能助理。串流回覆，系統提示詞讀自 prompts/assistant.md。
# ---------------------------------------------------------------------------

ASSISTANT_STARTERS = [
    "三種角色分別看得到什麼資料？",
    "住客本週服務量落後，我應該先查什麼？",
    "把這段口述整理成表單欄位：李伯今日步行訓練十五分鐘，中途需扶持，右膝有痛",
    "這套系統現在還缺哪些模組？",
]


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: list[ChatTurn]


@router.get("/assistant/status")
def assistant_status(user: deps.User = Depends(deps.current_user)) -> dict:
    return {
        "available": bool(config.LLM_API_KEY) and not config.DEMO_MODE,
        "model": config.LLM_MODEL if config.LLM_API_KEY else None,
        "starters": ASSISTANT_STARTERS,
        "persona_chars": len(assistant.prompt()),
    }


@router.post("/assistant/chat")
async def assistant_chat(body: ChatIn, user: deps.User = Depends(deps.current_user)):
    """SSE 串流。前端逐字接收，等待就變成閱讀。"""
    turns = [t.model_dump() for t in body.messages][-12:]   # 只帶最近幾輪，控成本
    question = next((t["content"] for t in reversed(turns) if t["role"] == "user"), "")
    short = question if len(question) <= 22 else question[:22] + "…"
    audit.write(user, "詢問助理", f"向智能助理提問「{short}」", "assistant", "-",
                details=[audit.change("提問內容", after=question)])

    async def events():
        try:
            async for piece in assistant.stream(turns):
                yield "data: " + json.dumps({"t": piece}, ensure_ascii=False) + "\n\n"
        except Exception as error:                      # noqa: BLE001
            yield "data: " + json.dumps(
                {"t": f"\n\n（發生錯誤：{type(error).__name__}）"}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
