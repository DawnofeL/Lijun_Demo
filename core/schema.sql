-- SEDNA CARE 原型资料表
-- 全部表带 facility_id 用于院舍隔离，带 is_deleted 走软删除，带建立时间。

CREATE TABLE IF NOT EXISTS facilities (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    district    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_no      TEXT NOT NULL UNIQUE,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    position      TEXT NOT NULL,          -- PT / PTA / OT / OTA / AA
    role          TEXT NOT NULL,          -- staff / supervisor / admin
    facility_id   TEXT NOT NULL,
    is_deleted    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS residents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bed_no         TEXT NOT NULL,
    name           TEXT NOT NULL,
    gender         TEXT NOT NULL,
    funding_type   TEXT NOT NULL,         -- 甲一買位 / 合約院舍資助宿位 / 院舍券 / 私位
    sc_flag        INTEGER NOT NULL DEFAULT 0,
    weekly_target  INTEGER NOT NULL DEFAULT 3,
    service_track  TEXT NOT NULL,         -- 資助復康 / 認知障礙症
    last_assessed  TEXT,                  -- 最近一次评估日期，可空
    facility_id    TEXT NOT NULL,
    is_deleted     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    UNIQUE (facility_id, bed_no),
    FOREIGN KEY (facility_id) REFERENCES facilities(id)
);

CREATE TABLE IF NOT EXISTS work_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date  TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    service_type  TEXT NOT NULL,
    service_track TEXT NOT NULL,
    resident_id   INTEGER NOT NULL,
    staff_id      INTEGER NOT NULL,
    facility_id   TEXT NOT NULL,
    status        TEXT NOT NULL,          -- 待接收 / 已接收 / 已完成 / 未能出席
    is_deleted    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (resident_id) REFERENCES residents(id),
    FOREIGN KEY (staff_id) REFERENCES staff(id),
    FOREIGN KEY (facility_id) REFERENCES facilities(id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON work_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_sessions_staff ON work_sessions(staff_id);
CREATE INDEX IF NOT EXISTS idx_sessions_facility ON work_sessions(facility_id);

-- 表单模板与提交分两张表。提交记录存模板代码加版本号，
-- 模板改版之后旧记录仍按当时的版本渲染。
CREATE TABLE IF NOT EXISTS form_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    version     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (code, version)
);

CREATE TABLE IF NOT EXISTS form_submissions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL,
    resident_id      INTEGER NOT NULL,
    template_code    TEXT NOT NULL,
    template_version INTEGER NOT NULL,
    data_json        TEXT NOT NULL,
    status           TEXT NOT NULL,       -- 已提交 / 已審批 / 已鎖定
    submitted_by     TEXT NOT NULL,
    submitted_at     TEXT NOT NULL,
    facility_id      TEXT NOT NULL,
    is_deleted       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES work_sessions(id),
    FOREIGN KEY (resident_id) REFERENCES residents(id)
);

CREATE INDEX IF NOT EXISTS idx_submissions_resident ON form_submissions(resident_id);
-- 合规看板的「已完成但未填表」是 NOT EXISTS (... WHERE x.session_id = s.id)。
-- 没有这个索引的话，每一节都要全表扫一遍 form_submissions，成本随两张表相乘。
-- 演示资料 3080 节时是 188ms，看不出问题；三间院舍跑三年是 15 万节，
-- 同一句查询要 18.7 秒，页面直接白掉。加上之后 65ms，快 288 倍。
-- 这类东西不会在演示里出现，只会在上线一年后出现。
CREATE INDEX IF NOT EXISTS idx_submissions_session ON form_submissions(session_id);

-- 只追加，没有更新和删除接口。
-- summary 是写入时就生成好的一句中文，界面直接显示，不让使用者读 JSON。
-- details 是结构化的逐栏变更，点开才看，栏位名也是中文。
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id     INTEGER,
    actor_name   TEXT NOT NULL,
    actor_role   TEXT NOT NULL,
    action       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    entity       TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    details_json TEXT,
    facility_id  TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL,
    assessed_at TEXT NOT NULL,
    assessed_by TEXT NOT NULL,
    summary     TEXT,
    facility_id TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (resident_id) REFERENCES residents(id)
);
