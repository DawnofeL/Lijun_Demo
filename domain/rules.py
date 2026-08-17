"""业务规则纯函数。不碰资料库、不碰请求，输入输出都是普通资料结构。

合规看板的所有判断都在这里，接口层只负责取数和拼装。
规则要改的时候只动这一个文件，改完能立刻跑测试验证。
"""

from datetime import date, datetime

import config

# ---- 评估周期 ---------------------------------------------------------------

ASSESSMENT_LEVELS = {
    "overdue": "已逾期",
    "due_soon": "即將到期",
    "normal": "正常",
    "never": "從未評估",
}


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def assessment_status(last_assessed: str | date | None, today: date | None = None) -> dict:
    """回传距离 180 天到期还有多少天，以及分级。

    从未评估视同已逾期处理，因为受牌照规管的院舍里「没有记录」和「超期」
    在稽查时的后果是一样的。
    """
    today = today or date.today()
    last = parse_date(last_assessed)

    if last is None:
        return {
            "level": "never",
            "level_label": ASSESSMENT_LEVELS["never"],
            "days_left": None,
            "last_assessed": None,
        }

    days_elapsed = (today - last).days
    days_left = config.ASSESSMENT_CYCLE_DAYS - days_elapsed

    if days_left < 0:
        level = "overdue"
    elif days_left <= config.ASSESSMENT_WARN_DAYS:
        level = "due_soon"
    else:
        level = "normal"

    return {
        "level": level,
        "level_label": ASSESSMENT_LEVELS[level],
        "days_left": days_left,
        "last_assessed": last.isoformat(),
    }


# ---- 周目标达成率 -----------------------------------------------------------

TARGET_LEVELS = {
    "met": "已達標",
    "at_risk": "有風險",
    "behind": "落後",
}


def target_status(completed: int, target: int) -> dict:
    """回传达成率百分比与红黄绿分级。

    目标为零时视同达标，避免除零，也避免把没有服务权益的住客标红。
    """
    if target <= 0:
        return {
            "completed": completed,
            "target": target,
            "rate": 100,
            "level": "met",
            "level_label": TARGET_LEVELS["met"],
        }

    rate = round(completed / target * 100)
    if rate >= 100:
        level = "met"
    elif rate >= 60:
        level = "at_risk"
    else:
        level = "behind"

    return {
        "completed": completed,
        "target": target,
        "rate": rate,
        "level": level,
        "level_label": TARGET_LEVELS[level],
    }


# ---- 节次状态归一 -----------------------------------------------------------

SESSION_BADGES = {
    "待接收": "pending",
    "已接收": "accepted",
    "已完成": "done",
    "未能出席": "absent",
}


def session_badge(status: str) -> str:
    """把资料库里的原始状态映射成界面上的徽章类型。"""
    return SESSION_BADGES.get(status, "pending")


# ---- 周区间 -----------------------------------------------------------------

def week_range(today: date | None = None, offset: int = 0) -> tuple[str, str]:
    """回传某一周的周一与周日。offset=0 本周，-1 上一周。达成率按自然周统计。"""
    today = today or date.today()
    monday = today.fromordinal(today.toordinal() - today.weekday() + offset * 7)
    sunday = today.fromordinal(monday.toordinal() + 6)
    return monday.isoformat(), sunday.isoformat()


def pick_week(mode: str = "auto", today: date | None = None) -> dict:
    """决定统计哪一周。

    本周才过一两天时，达成率必然全线落後，这个数字没有参考价值。
    所以 auto 模式下改看上一个完整周，并在回传体标明看的是哪一周，
    让使用者知道自己在看什麽，而不是默默换掉。
    """
    today = today or date.today()
    elapsed = today.weekday() + 1          # 本周已过天数，周一为 1

    if mode == "current":
        offset = 0
    elif mode == "last":
        offset = -1
    else:
        offset = 0 if elapsed >= 3 else -1

    start, end = week_range(today, offset)
    if offset == 0:
        label = f"本週（{start} 至今，已過 {elapsed} 天）"
    else:
        label = f"上一個完整週（{start} 至 {end}）"

    return {
        "from": start,
        "to": end,
        "offset": offset,
        "label": label,
        "auto_switched": mode == "auto" and offset != 0,
        "reason": "本週才開始，統計未具參考價值，已改為顯示上一個完整週。"
                  if (mode == "auto" and offset != 0) else "",
    }
