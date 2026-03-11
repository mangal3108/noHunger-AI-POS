from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrderItem(BaseModel):
    item_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)


class CreateOrderRequest(BaseModel):
    session_id: str
    restaurant_name: str
    delivery_address: str = Field(min_length=5)
    payment_method: str = "UPI"
    items: list[OrderItem]
    total_amount: float = Field(ge=0.0)
    currency: str = "INR"


class OrderRecord(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    restaurant_name: str
    delivery_address: str
    payment_method: str = "UPI"
    items: list[OrderItem]
    total_amount: float
    currency: str = "INR"
    order_status: str = "payment_pending"
    payment_status: str = "pending"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
