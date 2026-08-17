"""SEDNA CARE 院舍照護管理原型 · 入口。

启动顺序固定，任何一步依赖前一步：
建库 → 灌示范资料 → 载入知识库 → 挂接口路由 → 挂静态档案 → 起服务。
建库和灌资料都是幂等的，反复启动不会重复灌。
"""

import sys


def _check_dependencies() -> None:
    missing = []
    for module, package in (("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                            ("httpx", "httpx"), ("openpyxl", "openpyxl"),
                            ("multipart", "python-multipart")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        print("缺少相依套件：" + "、".join(missing))
        print("請先執行：pip install -r requirements.txt")
        sys.exit(1)


_check_dependencies()

import webbrowser  # noqa: E402
from threading import Timer  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import config  # noqa: E402
from core import db  # noqa: E402
from domain import seed  # noqa: E402

app = FastAPI(title="SEDNA CARE 院舍照護管理原型", version="0.1.0")


def bootstrap() -> None:
    fresh = db.init_db()
    if fresh or db.is_empty():
        stats = seed.seed_all()
        print("已建立示範資料：",
              f"{stats['facilities']} 間院舍、{stats['residents']} 位住客、"
              f"{stats['sessions']} 節、{stats['submissions']} 份表單")
    else:
        print("沿用現有資料庫：", config.DB_PATH)

    from knowledge import assistant, ingest
    chunk_count = ingest.load_corpus()
    print(f"知識庫已載入：{chunk_count} 個段落，來源 {'、'.join(ingest.stats()['sources'])}")
    print(f"助理提示詞已載入：{assistant.load_prompt()} 字")

    print()
    print("=" * 58)
    print("  示範帳號（密碼一律 " + seed.DEMO_PASSWORD + "）")
    print("  chan       職員     陳美儀 · 只看得到自己的節次")
    print("  wong       組長     黃淑芬 · 看得到本院舍全部")
    print("  admin      管理員   吳偉明 · 看得到三間院舍")
    print("=" * 58)
    print(f"  {config.DEMO_DATA_BANNER}")
    if not config.LLM_API_KEY and not config.DEMO_MODE:
        print("  未設定 LLM_API_KEY，知識庫問答將走預置答案")
    print("=" * 58)
    print()


def mount_routes() -> None:
    """接口挂在 /api 下，静态档案挂在根路径，两者不冲突。"""
    from api import (auth, residents, sessions, compliance, audit_view,
                     knowledge, roadmap, today)

    for module in (auth, residents, sessions, compliance, audit_view,
                   knowledge, roadmap, today):
        app.include_router(module.router, prefix="/api")

    app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "demo_mode": config.DEMO_MODE, "banner": config.DEMO_DATA_BANNER}


def main() -> None:
    import uvicorn

    bootstrap()
    mount_routes()

    url = f"http://{config.HOST}:{config.PORT}"
    print(f"服務啟動中：{url}")
    if config.OPEN_BROWSER:
        Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
