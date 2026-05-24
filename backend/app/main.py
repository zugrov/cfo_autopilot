"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import auth, imports, dashboard, obligations, ai_chat, onboarding, users, reports, audit

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Финансовый автопилот API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.cfo-autopilot.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(imports.router)
app.include_router(dashboard.router)
app.include_router(obligations.router)
app.include_router(ai_chat.router)
app.include_router(onboarding.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(audit.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
