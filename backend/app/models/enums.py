"""Shared domain enumerations used across models, schemas, and services."""
from enum import Enum


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class FailureReason(str, Enum):
    TEMPORARY_BANK_FAILURE = "TEMPORARY_BANK_FAILURE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    PAYMENT_METHOD_ISSUE = "PAYMENT_METHOD_ISSUE"
    CUSTOMER_ABANDONMENT = "CUSTOMER_ABANDONMENT"
    REPEATED_FAILURE = "REPEATED_FAILURE"
    MERCHANT_CONFIGURATION = "MERCHANT_CONFIGURATION"
    UNKNOWN = "UNKNOWN"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OpportunityStatus(str, Enum):
    OPEN = "OPEN"
    DECIDED = "DECIDED"
    EXECUTING = "EXECUTING"
    RECOVERED = "RECOVERED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"


class RecoveryActionType(str, Enum):
    """Controlled action space. The LLM may never invent actions outside this set."""

    DO_NOTHING = "DO_NOTHING"
    RETRY_NOW = "RETRY_NOW"
    RETRY_LATER = "RETRY_LATER"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    RESEND_PAYMENT_LINK = "RESEND_PAYMENT_LINK"
    ALTERNATE_PAYMENT_METHOD = "ALTERNATE_PAYMENT_METHOD"
    SEND_REMINDER = "SEND_REMINDER"
    ESCALATE_TO_MERCHANT = "ESCALATE_TO_MERCHANT"


class Timing(str, Enum):
    NOW = "NOW"
    MIN_15 = "15_MINUTES"
    MIN_30 = "30_MINUTES"
    HOUR_1 = "1_HOUR"
    HOUR_6 = "6_HOURS"
    HOUR_24 = "24_HOURS"


class AttemptAction(str, Enum):
    INITIAL = "INITIAL"
    RETRY = "RETRY"
    PAYMENT_LINK = "PAYMENT_LINK"
    REMINDER = "REMINDER"
    MANUAL = "MANUAL"


class AttemptStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class OutcomeResult(str, Enum):
    RECOVERED = "RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    PENDING = "PENDING"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"


class ExecutionChannel(str, Enum):
    """Distinguishes real Test Mode execution from simulation."""

    RAZORPAY_TEST_MODE = "RAZORPAY_TEST_MODE"
    SIMULATED = "SIMULATED"
