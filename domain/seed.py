"""示范资料生成。

姓名用港式繁体，资助类别取自社署四类宿位。节次状态按真实比例分布，
其中「未能出席」保持一定占比，合规看板和演示都要用到它。
所有资料仅供演示，界面上固定显示 config.DEMO_DATA_BANNER。
"""

import json
import random
from datetime import date, timedelta

import config
from core import db, security

random.seed(20260818)  # 固定种子，每次生成结果一致，演示可复现

FACILITIES = [
    ("facility-a", "頌康苑護理安老院", "沙田"),
    ("facility-b", "松栢園護老中心", "觀塘"),
    ("facility-c", "頤和軒院舍", "屯門"),
]

SURNAMES = list("陳李黃張梁何吳劉蔡鄭謝許羅周馮曾鍾麥胡")
GIVEN_M = ["國榮", "志強", "建華", "偉明", "家豪", "永強", "文傑", "俊傑", "德輝", "子軒"]
GIVEN_F = ["凱婷", "秀英", "婉玲", "美儀", "淑芬", "麗珍", "詠恩", "雅琳", "惠芳", "曉彤"]

FUNDING_TYPES = ["甲一買位", "合約院舍資助宿位", "院舍券", "私位"]
FUNDING_WEIGHTS = [0.32, 0.24, 0.26, 0.18]
SERVICE_TRACKS = ["資助復康", "認知障礙症"]
# 服务类型按轨道分池。认知障碍症轨道不该排肢体训练，反之亦然，
# 混排在懂业务的人眼里一眼就是假资料。
SERVICE_TYPES = {
    "資助復康": ["肢體幅度訓練", "步行訓練", "平衡訓練", "肌力訓練", "個別復康"],
    "認知障礙症": ["認知訓練", "現實導向訓練", "懷緬治療", "小組活動"],
}
POSITIONS = ["PT", "PTA", "OT", "OTA", "AA"]

STAFF_SEED = [
    # (staff_no, username, display_name, position, role, facility_id)
    ("PT001", "chan", "陳美儀", "PT", "staff", "facility-a"),
    ("PTA02", "lee", "李文傑", "PTA", "staff", "facility-a"),
    ("OT003", "wong", "黃淑芬", "OT", "supervisor", "facility-a"),
    ("PT004", "cheung", "張家豪", "PT", "staff", "facility-b"),
    ("OTA05", "leung", "梁詠恩", "OTA", "staff", "facility-b"),
    ("PT006", "ho", "何俊傑", "PT", "staff", "facility-c"),
    ("ADM01", "admin", "吳偉明", "AA", "admin", "facility-a"),
]

DEMO_PASSWORD = "demo1234"

FORM_TEMPLATE = {
    "code": "service_record",
    "title": "服務記錄表",
    "fields": [
        {"key": "completed", "label": "是否完成", "type": "select",
         "required": True, "options": ["完成", "部分完成", "未能進行"]},
        {"key": "cooperation", "label": "配合程度", "type": "select",
         "required": True, "options": ["良好", "一般", "欠佳"]},
        {"key": "duration", "label": "實際時長", "type": "number",
         "required": True, "unit": "分鐘"},
        {"key": "observation", "label": "觀察備註", "type": "textarea", "required": False},
    ],
}


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# 员工姓名不进住客名字池。同一个名字同时出现在治疗师和住客栏，
# 懂业务的人一眼看出是生成资料。
STAFF_NAMES = {name for _, _, name, _, _, _ in STAFF_SEED}


def _make_residents(facility_id: str, count: int, start_index: int) -> list[tuple]:
    rows = []
    today = date.today()
    for i in range(count):
        gender = random.choice(["男", "女"])
        for _ in range(20):
            name = random.choice(SURNAMES) + random.choice(GIVEN_M if gender == "男" else GIVEN_F)
            if name not in STAFF_NAMES:
                break
        bed_no = f"{chr(65 + i // 20)}{start_index + i:03d}"
        funding = random.choices(FUNDING_TYPES, weights=FUNDING_WEIGHTS)[0]
        track = random.choices(SERVICE_TRACKS, weights=[0.7, 0.3])[0]
        target = random.choice([2, 3, 3, 4, 5])

        # 评估日期分布：多数正常，少数临近到期，个别逾期，个别从未评估
        bucket = random.random()
        if bucket < 0.08:
            last_assessed = None
        elif bucket < 0.18:
            last_assessed = (today - timedelta(days=random.randint(181, 240))).isoformat()
        elif bucket < 0.34:
            last_assessed = (today - timedelta(days=random.randint(151, 179))).isoformat()
        else:
            last_assessed = (today - timedelta(days=random.randint(10, 145))).isoformat()

        rows.append((
            bed_no, name, gender, funding, 1 if random.random() < 0.15 else 0,
            target, track, last_assessed, facility_id, 0, _now(),
        ))
    return rows


def _make_sessions(residents: list[dict], staff_by_facility: dict, days_back: int = 90):
    rows = []
    today = date.today()
    for offset in range(days_back, -1, -1):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:            # 周末不排
            continue
        for facility_id, staff_list in staff_by_facility.items():
            pool = [r for r in residents if r["facility_id"] == facility_id]
            if not pool:
                continue
            for member in staff_list:
                slot = 8 * 60 + 30        # 08:30 起
                picks = random.sample(pool, min(len(pool), random.randint(6, 10)))
                for resident in picks:
                    length = random.choice([15, 20, 30])
                    start = f"{slot // 60:02d}:{slot % 60:02d}"
                    end_minutes = slot + length
                    end = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
                    slot = end_minutes + random.choice([0, 0, 5])

                    if offset == 0:
                        status = random.choices(
                            ["待接收", "已接收", "已完成", "未能出席"],
                            weights=[0.25, 0.35, 0.3, 0.1])[0]
                    else:
                        status = random.choices(
                            ["已完成", "未能出席"], weights=[0.88, 0.12])[0]

                    rows.append((
                        day.isoformat(), start, end,
                        random.choice(SERVICE_TYPES[resident["service_track"]]),
                        resident["service_track"],
                        resident["id"], member["id"], facility_id, status, 0, _now(),
                    ))
                    if slot > 17 * 60:
                        break
    return rows


def _make_submissions(sessions: list[dict], staff_by_id: dict) -> list[tuple]:
    rows = []
    for session in sessions:
        if session["status"] != "已完成":
            continue
        if random.random() > 0.82:        # 刻意留一部分已完成但未填表，合规看板要用
            continue
        data = {
            "completed": random.choices(["完成", "部分完成"], weights=[0.85, 0.15])[0],
            "cooperation": random.choices(["良好", "一般", "欠佳"], weights=[0.6, 0.3, 0.1])[0],
            "duration": random.choice([15, 20, 25, 30]),
            "observation": random.choice([
                "", "", "情緒穩定，配合良好。", "右膝仍有痛楚，已放緩幅度。",
                "訓練期間需較多口頭提示。", "較上週有進步。",
            ]),
        }
        status = random.choices(["已提交", "已審批", "已鎖定"], weights=[0.2, 0.3, 0.5])[0]
        rows.append((
            session["id"], session["resident_id"],
            FORM_TEMPLATE["code"], 1, json.dumps(data, ensure_ascii=False),
            status, staff_by_id[session["staff_id"]], session["session_date"] + "T17:00:00",
            session["facility_id"], 0,
        ))
    return rows


def seed_all() -> dict:
    """灌入全部示范资料。回传统计，供启动日志打印。"""
    now = _now()

    db.execute_many(
        "INSERT INTO facilities(id, name, district, created_at) VALUES (?,?,?,?)",
        [(fid, name, district, now) for fid, name, district in FACILITIES],
    )

    db.execute_many(
        "INSERT INTO staff(staff_no, username, password_hash, display_name, position,"
        " role, facility_id, is_deleted, created_at) VALUES (?,?,?,?,?,?,?,0,?)",
        [(no, username, security.hash_password(DEMO_PASSWORD), name, position,
          role, facility_id, now)
         for no, username, name, position, role, facility_id in STAFF_SEED],
    )

    resident_rows = []
    for index, (facility_id, _, _) in enumerate(FACILITIES):
        resident_rows += _make_residents(facility_id, random.randint(28, 34), 1 + index * 40)
    db.execute_many(
        "INSERT INTO residents(bed_no, name, gender, funding_type, sc_flag, weekly_target,"
        " service_track, last_assessed, facility_id, is_deleted, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        resident_rows,
    )

    db.execute(
        "INSERT INTO form_templates(code, version, title, fields_json, is_active,"
        " created_by, created_at) VALUES (?,?,?,?,1,?,?)",
        (FORM_TEMPLATE["code"], 1, FORM_TEMPLATE["title"],
         json.dumps(FORM_TEMPLATE["fields"], ensure_ascii=False), "系統", now),
    )

    residents = db.query("SELECT id, facility_id, service_track FROM residents")
    staff = db.query("SELECT id, display_name, facility_id FROM staff WHERE role != 'admin'")
    staff_by_facility: dict[str, list] = {}
    for member in staff:
        staff_by_facility.setdefault(member["facility_id"], []).append(member)
    staff_by_id = {m["id"]: m["display_name"] for m in staff}

    db.execute_many(
        "INSERT INTO work_sessions(session_date, start_time, end_time, service_type,"
        " service_track, resident_id, staff_id, facility_id, status, is_deleted, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        _make_sessions(residents, staff_by_facility),
    )

    sessions = db.query(
        "SELECT id, resident_id, staff_id, facility_id, session_date, status FROM work_sessions"
    )
    db.execute_many(
        "INSERT INTO form_submissions(session_id, resident_id, template_code,"
        " template_version, data_json, status, submitted_by, submitted_at,"
        " facility_id, is_deleted) VALUES (?,?,?,?,?,?,?,?,?,?)",
        _make_submissions(sessions, staff_by_id),
    )

    assessment_rows = []
    for resident in db.query("SELECT id, last_assessed, facility_id FROM residents"):
        if resident["last_assessed"]:
            assessment_rows.append((
                resident["id"], resident["last_assessed"], "系統匯入",
                "歷史評估記錄", resident["facility_id"], now,
            ))
    db.execute_many(
        "INSERT INTO assessments(resident_id, assessed_at, assessed_by, summary,"
        " facility_id, created_at) VALUES (?,?,?,?,?,?)",
        assessment_rows,
    )

    _seed_audit(staff_by_id)

    return {
        "facilities": len(FACILITIES),
        "staff": len(STAFF_SEED),
        "residents": len(resident_rows),
        "sessions": len(sessions),
        "submissions": db.query_one("SELECT COUNT(*) AS n FROM form_submissions")["n"],
    }


# ---------------------------------------------------------------------------
# 示范留痕。留痕页如果只有当次登入那一条，就演示不出「谁在什么时候动过什么」，
# 所以补一批过去几天的历史纪录。全部是生成的示范资料。
# ---------------------------------------------------------------------------

def _seed_audit(staff_by_id: dict) -> None:
    import json as _json
    from core import audit as _audit

    staff = db.query(
        "SELECT id, display_name, role, facility_id FROM staff WHERE role != 'admin'")
    role_label = {"staff": "職員", "supervisor": "組長", "admin": "管理員"}
    residents = db.query("SELECT id, name, bed_no, facility_id FROM residents")

    from datetime import datetime as _dt
    rows = []
    now = date.today()
    this_hour = _dt.now().hour

    def add(days_ago: int, hour: int, minute: int, member: dict,
            action: str, summary: str, entity: str, entity_id, details):
        # 今天的纪录不排到当前时刻之后
        if days_ago == 0 and hour >= this_hour:
            return
        stamp = (now - timedelta(days=days_ago)).isoformat() + \
                f"T{hour:02d}:{minute:02d}:{random.randint(0, 59):02d}"
        rows.append((
            member["id"], member["display_name"], role_label.get(member["role"], member["role"]),
            action, summary, entity, str(entity_id),
            _json.dumps(details, ensure_ascii=False) if details else None,
            member["facility_id"], stamp,
        ))

    for days_ago in range(6, -1, -1):
        if (now - timedelta(days=days_ago)).weekday() >= 5:
            continue
        for member in staff:
            pool = [r for r in residents if r["facility_id"] == member["facility_id"]]
            if not pool:
                continue

            add(days_ago, 8, random.randint(20, 40), member,
                "登入", "登入系統", "staff", member["id"], None)

            for resident in random.sample(pool, min(len(pool), random.randint(2, 4))):
                completed = random.choice(["完成", "完成", "部分完成"])
                cooperation = random.choice(["良好", "良好", "一般", "欠佳"])
                add(days_ago, random.randint(9, 16), random.randint(0, 59), member,
                    "提交服務表單",
                    f"提交 {resident['name']}（{resident['bed_no']}）的服務表單，"
                    f"記錄為「{completed}、配合{cooperation}」",
                    "submission", resident["id"],
                    [_audit.change("是否完成", after=completed),
                     _audit.change("配合程度", after=cooperation),
                     _audit.change("實際時長", after=f"{random.choice([15, 20, 25, 30])} 分鐘")])

            if member["role"] == "supervisor" and random.random() < 0.7:
                resident = random.choice(pool)
                add(days_ago, 17, random.randint(0, 40), member,
                    "審批表單",
                    f"覆核並審批 {resident['name']}（{resident['bed_no']}）的服務表單",
                    "submission", resident["id"],
                    [_audit.change("表單狀態", before="已提交", after="已審批"),
                     _audit.change("覆核人", after=member["display_name"])])

            if member["role"] == "supervisor" and random.random() < 0.3:
                resident = random.choice(pool)
                old_target = random.choice([2, 3])
                add(days_ago, random.randint(10, 15), random.randint(0, 59), member,
                    "修改住客資料",
                    f"調整 {resident['name']}（{resident['bed_no']}）的每週目標節數",
                    "resident", resident["id"],
                    [_audit.change("每週目標節數", before=old_target, after=old_target + 1),
                     _audit.change("調整原因", after="復康計劃更新")])

    rows.sort(key=lambda r: r[-1])
    db.execute_many(
        "INSERT INTO audit_log(actor_id, actor_name, actor_role, action, summary,"
        " entity, entity_id, details_json, facility_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
