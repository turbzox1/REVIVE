"""Health check endpoints."""
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter()


@router.get("/health/db")
def database_health() -> dict:
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
        return {"status": "ok", "database": "postgresql", "version": version}
    except Exception as exc:  # pragma: no cover - surfaced via HTTP status
        return {"status": "error", "detail": str(exc)}
