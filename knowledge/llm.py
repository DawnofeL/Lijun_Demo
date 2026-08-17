"""模型客户端。

任何 OpenAI 相容端点都可以，换个环境变量即可。
没有设定密钥或 DEMO_MODE 打开时不发请求，由呼叫端走降级路径，
保证现场断网也能演示完整流程。
"""

import httpx

import config


def available() -> bool:
    return bool(config.LLM_API_KEY) and not config.DEMO_MODE


async def complete(system: str, user_message: str, temperature: float = 0.0) -> str:
    """回传模型输出。呼叫前请先用 available() 判断。"""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{config.LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            },
        )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
