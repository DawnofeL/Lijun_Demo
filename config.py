"""集中所有可变量。密钥一律走环境变量，读不到给仅供演示的默认值。"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"
CORPUS_DIR = BASE_DIR / "knowledge" / "corpus"

DATA_DIR.mkdir(exist_ok=True)


def _load_env(path: Path = BASE_DIR / ".env") -> None:
    """极简 .env 载入器。不引 python-dotenv，少一个相依。

    已经存在的环境变数优先，命令列上临时指定的值不会被档案覆盖。
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env()

# ---- 资料库 -----------------------------------------------------------------
DB_PATH = Path(os.getenv("SEDNA_DB", DATA_DIR / "sedna_care.db"))
SCHEMA_PATH = BASE_DIR / "core" / "schema.sql"

# ---- 签名 -------------------------------------------------------------------
SECRET = os.getenv("SEDNA_SECRET", "demo-only-secret-do-not-use-in-production")
TOKEN_TTL_HOURS = 12

# ---- 模型 -------------------------------------------------------------------
# 任何 OpenAI 相容端点都可以：DashScope / DeepSeek / OpenAI / 本地 vLLM
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")

# 打开后知识库问答不发请求，直接走预置答案。现场没有网络时用。
DEMO_MODE = os.getenv("SEDNA_DEMO_MODE", "").lower() in ("1", "true", "yes")

# ---- 服务 -------------------------------------------------------------------
HOST = os.getenv("SEDNA_HOST", "127.0.0.1")
PORT = int(os.getenv("SEDNA_PORT", "8000"))
OPEN_BROWSER = os.getenv("SEDNA_OPEN_BROWSER", "1") != "0"

# ---- 业务常数 ---------------------------------------------------------------
ASSESSMENT_CYCLE_DAYS = 180          # 评估周期
ASSESSMENT_WARN_DAYS = 30            # 距到期几天内算临近
DEMO_DATA_BANNER = "示範資料，非真實住客"
