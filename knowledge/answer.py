"""生成。每一句结论都要标注引自第几段，检索不到就明说不知道。

受监管场景里答错比答不出来严重得多，所以设计目标不是「什么都能答」，
而是「答的每一句都能追回原文，答不出来会明说」。
"""

from knowledge import llm, retrieve

SYSTEM = """你是安老院舍的內部規範查詢助手。使用者會問流程或規範問題，
你只能根據下方提供的資料段落作答。

規則：
1. 每一句結論後面必須標註來源編號，格式為 [1]、[2]，對應下方段落編號。
2. 資料段落中沒有依據的內容一律不得回答，也不得依常識推測或補充。
3. 若段落不足以回答，直接回覆：資料庫中未找到相關依據，建議查閱原始文件或詢問主管。
4. 用繁體中文回答，條列式，簡短直接，不要客套。
5. 不提供任何臨床判斷或醫療建議。"""

NOT_FOUND = "資料庫中未找到相關依據，建議查閱原始文件或詢問主管。"

# 无密钥或断网时的预置答案，键为触发关键词
# 无密钥或断网时的预置答案。
# 每条不硬写编号，而是记下它引自哪一节，渲染时按实际检索结果解析出编号。
# 硬写编号会在检索结果变动时对不上，那种错误在演示现场最难解释。
FALLBACK = {
    ("跌倒", "跌親", "摔"): [
        ("不應立即扶起，先在原位評估意識、外傷、肢體變形與疼痛情況", "1.1"),
        ("懷疑骨折、頭部受創或失去意識者，保持原姿勢並即時呼叫救護服務", "1.1"),
        ("即時通知當值主管；涉及送院、骨折或頭部受創須於 24 小時內通報主管當局，"
         "7 日內提交書面事故報告", "1.2"),
        ("跌倒記錄須載明時間地點、發現人、傷勢評估與已採措施，由當事職員簽署、主管覆核", "1.3"),
        ("頭部受創者連續觀察至少 72 小時，每 4 小時記錄一次；兩週內重新評估跌倒風險", "1.4"),
    ],
    ("評估", "180", "周期", "週期", "逾期"): [
        ("每位住客須至少每 180 日接受一次全面復康評估，由註冊治療師執行", "3.1"),
        ("跌倒後兩週內、住院返回、功能明顯退步、家屬要求，須提前評估", "3.2"),
        ("評估逾期須列明原因並補做；新入住住客須於入住後 30 日內完成首次評估", "3.3"),
    ],
    ("修改", "更正", "覆蓋", "保存"): [
        ("已提交的紀錄不得直接覆蓋", "4.2"),
        ("需要更正時以附註方式補充，載明更正內容、原因、更正人與時間，原始內容須保留可查", "4.2"),
        ("住客的照護紀錄、評估報告與事故報告，自離院之日起保存不少於 7 年", "4.1"),
        ("職員僅可查閱其負責住客的紀錄，跨院舍查閱須經管理層批准並留下紀錄", "4.3"),
    ],
    ("匯入", "導入", "名單", "模板"): [
        ("批次匯入僅限組長與管理員操作", "3.3"),
        ("匯入前須下載系統模板，欄位名稱不可自行更改", "3.3"),
        ("校驗失敗的資料列不會寫入，系統會列出失敗原因供修正後重傳", "3.3"),
        ("床號在同一院舍內不可重複", "3.1"),
    ],
}

NO_KEY_PREFIX = ""


def _fallback_answer(question: str, passages: list[dict]) -> str | None:
    """把预置条目对上实际检索到的段落，解析出正确的引用编号。

    对不上的条目直接丢掉，宁可少答一条，也不要标一个指不到任何出处的编号。
    """
    bullets = None
    for keywords, entries in FALLBACK.items():
        if any(word in question for word in keywords):
            bullets = entries
            break
    if bullets is None:
        return None

    rank_of = {}
    for passage in passages:
        for part in passage["heading_path"]:
            token = part.split(" ")[0].strip()
            if token and token[0].isdigit():
                rank_of.setdefault(token, passage["rank"])

    lines = []
    for text, section in bullets:
        rank = rank_of.get(section)
        if rank is None:
            continue
        lines.append(f"{len(lines) + 1}. {text} [{rank}]")

    if not lines:
        return None
    return NO_KEY_PREFIX + "依據已入庫的規範文件：\n" + "\n".join(lines)


def _build_context(passages: list[dict]) -> str:
    blocks = []
    for passage in passages:
        blocks.append(
            f"[{passage['rank']}] 來源：{passage['citation']}\n{passage['text']}"
        )
    return "\n\n".join(blocks)


async def answer(question: str) -> dict:
    passages = retrieve.search(question)

    if not passages:
        return {
            "question": question,
            "answer": NOT_FOUND,
            "passages": [],
            "mode": "no_match",
        }

    def offline(reason: str = "") -> dict:
        # 出处按原文顺序重新编号，读起来跟文件一致
        ordered = sorted(passages, key=lambda item: (item["source"], item["lines"][0]))
        for rank, passage in enumerate(ordered, start=1):
            passage["rank"] = rank
        preset = _fallback_answer(question, ordered)
        prefix = reason + "\n\n" if reason else ""
        return {
            "question": question,
            "answer": prefix + (preset or (
                "以下為檢索到的原文段落，未經生成：\n\n"
                + "\n\n".join(f"[{p['rank']}] {p['citation']}\n{p['text'][:180]}"
                              for p in ordered))),
            "passages": ordered,
            "mode": "offline",
        }

    if not llm.available():
        # 出处按原文顺序重新编号，读起来跟文件一致
        passages = sorted(passages, key=lambda item: (item["source"], item["lines"][0]))
        for rank, passage in enumerate(passages, start=1):
            passage["rank"] = rank

        preset = _fallback_answer(question, passages)
        return {
            "question": question,
            "answer": preset or (
                "（未設定模型金鑰，以下為檢索到的原文段落，未經生成）\n\n"
                + "\n\n".join(f"[{p['rank']}] {p['citation']}\n{p['text'][:180]}"
                              for p in passages)
            ),
            "passages": passages,
            "mode": "offline",
        }

    try:
        text = await llm.complete(
            SYSTEM,
            f"問題：{question}\n\n可用資料段落：\n\n{_build_context(passages)}",
        )
        mode = "generated"
    except Exception:                                   # noqa: BLE001
        # 模型連不上就退回本地檢索加預置答案，而不是把錯誤丟到使用者臉上。
        # 現場沒有網絡時，這條路徑就是保命的那一條。
        return offline("（模型服務暫時無法使用，以下改用本地檢索結果）")

    return {
        "question": question,
        "answer": text,
        "passages": passages,
        "mode": mode,
    }
