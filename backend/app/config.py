import os

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DATA_DIR = os.path.join(ROOT_DIR, "data")
TRANSFORMER_LOSSES_PATH = os.path.join(DATA_DIR, "transformer_losses.xlsx")
THEFT_CASES_PATH = os.path.join(DATA_DIR, "theft_cases.xlsx")

BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
DB_PATH = os.path.join(BACKEND_DIR, "vidyutiq.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

USER_COOKIE_NAME = "vidyutiq_uid"
TOOL_CACHE_TTL_SECONDS = 300

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
