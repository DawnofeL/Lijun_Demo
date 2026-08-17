"""检索。关键词加权打分，回传带出处的段落。

刻意不上向量检索。规范问答的查询词和原文用词高度重合，
关键词加权在这个场景效果稳定且完全可解释，出错能立刻看出是哪一步的问题。
资料量再大一个量级时再换，届时介面不变。

打分只算二元词与英数词，不算单个汉字。单字在中文里太泛，
「今天天氣如何」里的「今」「如」「何」会跟大量段落沾边，
只算二元词才能把这类无关提问挡在门外。
"""

import math

from knowledge.ingest import Chunk, index, tokenize

HEADING_WEIGHT = 2.5      # 标题命中权重高于正文
MIN_SCORE = 1.2           # 低于此分视为无关，宁可回传空也不硬凑


def _meaningful(tokens: set) -> set:
    """只留二元词与英数词，滤掉单个汉字。"""
    return {t for t in tokens if len(t) >= 2 or t.isascii()}


def _score(chunk: Chunk, query_tokens: set) -> float:
    if not query_tokens:
        return 0.0

    heading_tokens = _meaningful(tokenize(" ".join(chunk.heading_path)))
    body_tokens = _meaningful(chunk.tokens)

    body_hits = len(query_tokens & body_tokens)
    heading_hits = len(query_tokens & heading_tokens)

    if body_hits == 0 and heading_hits == 0:
        return 0.0

    raw = body_hits + heading_hits * HEADING_WEIGHT
    # 长度归一，避免长段仅凭字数占优
    normaliser = 1 + math.log(1 + len(chunk.text) / 200)
    return raw / normaliser


def search(question: str, top_k: int = 4) -> list[dict]:
    query_tokens = _meaningful(tokenize(question))
    scored = []
    for chunk in index():
        score = _score(chunk, query_tokens)
        if score >= MIN_SCORE:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for rank, (score, chunk) in enumerate(scored[:top_k], start=1):
        payload = chunk.as_dict()
        payload["rank"] = rank
        payload["score"] = round(score, 3)
        results.append(payload)
    return results
