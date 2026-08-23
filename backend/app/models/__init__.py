"""Model package: importing members registers every table on Base.metadata."""
from app.db.base import Base
from app.models.catalog import Customer, Merchant, Order, Payment, PaymentAttempt
from app.models.ops import MerchantPolicy, WebhookEvent
from app.models.recovery import (
    ModelPrediction,
    RecoveryAction,
    RecoveryOpportunity,
    RecoveryOutcome,
)

__all__ = [
    "Base",
    "Customer",
    "Merchant",
    "MerchantPolicy",
    "ModelPrediction",
    "Order",
    "Payment",
    "PaymentAttempt",
    "RecoveryAction",
    "RecoveryOpportunity",
    "RecoveryOutcome",
    "WebhookEvent",
]
