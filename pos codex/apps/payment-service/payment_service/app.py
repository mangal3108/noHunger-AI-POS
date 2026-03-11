from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from packages.contracts.events import PaymentCompletedEvent

from .settings import settings

SUPPORTED_PAYMENT_METHODS = ("UPI", "CARD", "NETBANKING", "WALLET")


class CreatePaymentLinkRequest(BaseModel):
    order_id: str
    amount: float = Field(ge=0.0)
    currency: str = "INR"
    method: str = "UPI"


class PaymentLinkResponse(BaseModel):
    provider: str
    order_id: str
    amount: float
    method: str
    payment_id: str
    payment_link: str
    expires_at: str


app = FastAPI(title="Payment Service", version="0.1.0")
_payment_links: dict[str, dict] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/payments/methods")
async def payment_methods() -> dict[str, list[str]]:
    return {"methods": list(SUPPORTED_PAYMENT_METHODS)}


@app.post("/payments/link", response_model=PaymentLinkResponse)
async def create_payment_link(request: CreatePaymentLinkRequest) -> PaymentLinkResponse:
    method = request.method.upper().strip()
    if method not in SUPPORTED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported payment method '{request.method}'. Allowed: {', '.join(SUPPORTED_PAYMENT_METHODS)}",
        )

    payment_id = f"pay_{uuid4().hex[:12]}"
    link = (
        "https://payments.local/pay"
        f"?order_id={request.order_id}&payment_id={payment_id}&amount={request.amount}&method={method}"
    )
    expires_at = datetime.now(timezone.utc).isoformat()
    _payment_links[payment_id] = {
        "order_id": request.order_id,
        "amount": request.amount,
        "currency": request.currency,
        "method": method,
    }
    return PaymentLinkResponse(
        provider=settings.payment_provider,
        order_id=request.order_id,
        amount=request.amount,
        method=method,
        payment_id=payment_id,
        payment_link=link,
        expires_at=expires_at,
    )


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None)) -> dict[str, str]:
    if not x_razorpay_signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature.")

    raw_body = await request.body()
    expected = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    payload = json.loads(raw_body.decode("utf-8"))
    event_name = payload.get("event")
    if event_name != "payment.captured":
        return {"status": "ignored", "reason": f"unsupported event {event_name}"}

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment_entity.get("order_id")
    payment_id = payment_entity.get("id")
    amount = float(payment_entity.get("amount", 0.0))
    currency = payment_entity.get("currency", "INR")
    if amount > 1000:
        amount = round(amount / 100.0, 2)

    if not order_id or not payment_id:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")

    event = PaymentCompletedEvent(
        order_id=order_id,
        payment_id=payment_id,
        provider=settings.payment_provider,
        amount=amount,
        currency=currency,
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.order_service_url}/events/payment.completed",
            json=event.model_dump(),
        )
        response.raise_for_status()
    return {"status": "accepted", "event_type": event.event_type}
