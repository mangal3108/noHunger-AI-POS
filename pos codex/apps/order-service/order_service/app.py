from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from packages.contracts.events import PaymentCompletedEvent
from packages.contracts.order import CreateOrderRequest, OrderRecord

from .store import OrderStore


app = FastAPI(title="Order Service", version="0.1.0")
store = OrderStore()
SUPPORTED_PAYMENT_METHODS = ("UPI", "CARD", "NETBANKING", "WALLET", "COD")


class InventoryItemRecord(BaseModel):
    item_name: str
    unit_price: float = Field(ge=0.0)
    stock_qty: int = Field(ge=0)
    is_available: bool
    category: str = "Chef Specials"
    description: str = ""
    updated_at: str


class InventoryUpsertRequest(BaseModel):
    unit_price: float = Field(ge=0.0)
    stock_qty: int = Field(ge=0)
    is_available: bool = True


class AdminNotification(BaseModel):
    id: int
    type: str
    message: str
    order_id: str | None = None
    is_read: bool
    created_at: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/orders", response_model=OrderRecord)
async def create_order(request: CreateOrderRequest) -> OrderRecord:
    if not request.items:
        raise HTTPException(status_code=400, detail="Order must include at least one item.")
    if not request.delivery_address.strip():
        raise HTTPException(status_code=400, detail="Delivery address is required.")
    method = (request.payment_method or "UPI").upper().strip()
    if method not in SUPPORTED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported payment method '{request.payment_method}'. Allowed: {', '.join(SUPPORTED_PAYMENT_METHODS)}",
        )
    request.payment_method = method
    try:
        return store.create_order(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/orders/{order_id}", response_model=OrderRecord)
async def get_order(order_id: str) -> OrderRecord:
    record = store.get_order(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")
    return record


@app.post("/events/payment.completed", response_model=OrderRecord)
async def handle_payment_completed(event: PaymentCompletedEvent) -> OrderRecord:
    updated = store.mark_payment_completed(event)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found for payment event.")
    return updated


@app.post("/orders/{order_id}/payment/cod", response_model=OrderRecord)
async def mark_cod_payment(order_id: str) -> OrderRecord:
    updated = store.mark_cash_on_delivery(order_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found for COD payment.")
    return updated


@app.get("/payment-methods")
async def payment_methods() -> dict[str, list[str]]:
    return {"methods": list(SUPPORTED_PAYMENT_METHODS)}


@app.get("/menu")
async def menu() -> list[dict[str, Any]]:
    return store.get_menu_items()


@app.get("/admin/orders", response_model=list[OrderRecord])
async def admin_orders(limit: int = 50) -> list[OrderRecord]:
    return store.list_orders(limit=max(1, min(limit, 200)))


@app.get("/admin/inventory", response_model=list[InventoryItemRecord])
async def admin_inventory() -> list[InventoryItemRecord]:
    return [InventoryItemRecord(**row) for row in store.list_inventory()]


@app.put("/admin/inventory/{item_name}", response_model=InventoryItemRecord)
async def admin_upsert_inventory(item_name: str, request: InventoryUpsertRequest) -> InventoryItemRecord:
    updated = store.upsert_inventory_item(
        item_name=item_name,
        unit_price=request.unit_price,
        stock_qty=request.stock_qty,
        is_available=request.is_available,
    )
    return InventoryItemRecord(**updated)


@app.get("/admin/notifications", response_model=list[AdminNotification])
async def admin_notifications(unread_only: bool = False, limit: int = 100) -> list[AdminNotification]:
    rows = store.list_notifications(unread_only=unread_only, limit=max(1, min(limit, 500)))
    return [AdminNotification(**row) for row in rows]


@app.post("/admin/notifications/{notification_id}/read", response_model=AdminNotification)
async def admin_mark_notification_read(notification_id: int) -> AdminNotification:
    row = store.mark_notification_read(notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return AdminNotification(**row)
