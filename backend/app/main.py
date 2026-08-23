"""REVIVE — Autonomous Revenue Recovery & Decision Engine. FastAPI entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    logger.info("startup", extra={"event_data": {"env": settings.APP_ENV}})
    yield
    logger.info("shutdown")


app = FastAPI(
    title="REVIVE API",
    description="Autonomous Revenue Recovery & Decision Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
