"""智能助理。系统提示词读自 prompts/assistant.md，不写死在程式码里。

回覆走 SSE 逐字串流。串流不只是好看：模型第一个字出来通常要一两秒，
一次性回传的话使用者会以为系统卡住了。逐字吐出来，等待就变成了阅读。

助理回答的是流程与系统问题。规范条文类的问题会被引导去「规范问答」，
因为那里每句都标注原文出处，而助理凭印象说的条文可能过时。
"""

import json
from pathlib import Path
from typing import AsyncIterator

import httpx

import config

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "assistant.md"

_system_prompt: str = ""


def load_prompt() -> int:
    """启动时读入。回传字元数，供启动日志打印。"""
    global _system_prompt
    if PROMPT_PATH.exists():
        _system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    return len(_system_prompt)


def prompt() -> str:
    return _system_prompt


OFFLINE_REPLY = (
    "目前未設定模型金鑰，助理無法回覆。\n\n"
    "設定方式：把專案根目錄的 .env.example 複製為 .env，填入 LLM_API_KEY 後重啟。\n"
    "沒有金鑰時，「規範問答」仍可正常使用，那一塊走的是本地檢索加預置答案。"
)


async def stream(messages: list[dict]) -> AsyncIterator[str]:
    """把模型输出逐段吐出来。呼叫端负责包成 SSE。"""
    if not config.LLM_API_KEY or config.DEMO_MODE:
        for chunk in OFFLINE_REPLY:
            yield chunk
        return

    payload = {
        "model": config.LLM_MODEL,
        "temperature": 0.4,
        "stream": True,
        "messages": [{"role": "system", "content": _system_prompt}] + messages,
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream(
                "POST",
                f"{config.LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "ignore")[:200]
                    yield f"模型服務回應異常（{response.status_code}）：{body}"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {})
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    piece = delta.get("content")
                    if piece:
                        yield piece
    except httpx.HTTPError as error:
        yield f"\n\n（連線中斷：{type(error).__name__}）"
