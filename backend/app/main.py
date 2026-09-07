from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.data_cache import warm_cache
from app.db import init_db
from app.deps import get_current_user_id
from app.routers import chat, sessions
from app.schemas import MeOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    warm_cache()
    yield


app = FastAPI(title="Sarthi API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(chat.router)


@app.get("/api/me", response_model=MeOut)
def me(user_id: str = Depends(get_current_user_id)):
    return MeOut(user_id=user_id)


@app.get("/api/health")
def health():
    return {"status": "ok"}
