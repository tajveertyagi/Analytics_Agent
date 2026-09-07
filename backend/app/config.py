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
