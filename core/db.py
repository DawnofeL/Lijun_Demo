"""资料库薄封装。全篇只有这里开连接。"""

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

import config


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql: str, args: Iterable[Any] = ()) -> list[dict]:
    """读，返回字典列表。"""
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, tuple(args)).fetchall()]


def query_one(sql: str, args: Iterable[Any] = ()) -> dict | None:
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql: str, args: Iterable[Any] = ()) -> int:
    """写，返回新增行的 id（非 INSERT 时返回受影响行数）。"""
    with connect() as conn:
        cur = conn.execute(sql, tuple(args))
        return cur.lastrowid if cur.lastrowid else cur.rowcount


def execute_many(sql: str, rows: Iterable[Iterable[Any]]) -> int:
    with connect() as conn:
        cur = conn.executemany(sql, [tuple(r) for r in rows])
        return cur.rowcount


def init_db() -> bool:
    """建表。幂等，已存在就跳过。回传是否为首次建立。"""
    fresh = not config.DB_PATH.exists()
    schema = config.SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema)
    return fresh


def is_empty() -> bool:
    """资料库有没有灌过示范资料。"""
    row = query_one("SELECT COUNT(*) AS n FROM facilities")
    return (row or {}).get("n", 0) == 0
