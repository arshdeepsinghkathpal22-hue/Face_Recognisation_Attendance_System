from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.attendance import router as attendance_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.teacher import router as teacher_router
from app.config import DB_PATH, FRONTEND_ORIGIN, SESSION_SECRET
from app.db import initialize_db


def create_app(db_path: str | Path = DB_PATH) -> FastAPI:
    resolved_db_path = str(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_db(db_path=app.state.db_path)
        yield

    app = FastAPI(title="Attendance Portal API", version="1.0.0", lifespan=lifespan)
    app.state.db_path = resolved_db_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie="attendance_session",
        max_age=60 * 60 * 8,
        same_site="lax",
        https_only=False,
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(auth_router)
    app.include_router(attendance_router)
    app.include_router(teacher_router)
    app.include_router(admin_router)
    return app


app = create_app()
