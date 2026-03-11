from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    occurred_at: str = Field(default_factory=utc_now_iso)


class PaymentCompletedEvent(BaseEvent):
    event_type: str = "payment.completed"
    order_id: str
    payment_id: str
    provider: str
    amount: float
    currency: str = "INR"
