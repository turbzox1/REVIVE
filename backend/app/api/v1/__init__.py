from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.recovery import router as recovery_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.evaluation import router as evaluation_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(recovery_router)
api_router.include_router(webhooks_router, tags=["webhooks"])
api_router.include_router(evaluation_router)
