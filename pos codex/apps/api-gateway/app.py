from pathlib import Path
import sys
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

load_dotenv()
AI_AGENT_SERVICE_URL = os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")
API_GATEWAY_PORT = int(os.getenv("API_GATEWAY_PORT", "8000"))
FRONTEND_DIR = ROOT / "apps" / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "index.html"
FRONTEND_ADMIN_INDEX = FRONTEND_DIR / "admin.html"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class InventoryUpdateRequest(BaseModel):
    unit_price: float = Field(ge=0.0)
    stock_qty: int = Field(ge=0)
    is_available: bool = True


app = FastAPI(title="API Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_model=None)
async def home():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("https://frontend-gamma-six-45.vercel.app/")


@app.get("/admin", response_model=None)
async def admin_home():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("https://frontend-gamma-six-45.vercel.app/admin")


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    return await _proxy_json(
        "POST",
        f"{AI_AGENT_SERVICE_URL}/chat",
        json=request.model_dump(),
    )


@app.get("/menu")
async def menu() -> dict | list:
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/menu")


@app.get("/payment-methods")
async def payment_methods() -> dict | list:
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/payment-methods")


@app.get("/admin/orders")
async def admin_orders(limit: int = 50) -> dict | list:
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/admin/orders", params={"limit": limit})


@app.get("/admin/inventory")
async def admin_inventory() -> dict | list:
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/admin/inventory")


@app.put("/admin/inventory/{item_name}")
async def admin_update_inventory(item_name: str, request: InventoryUpdateRequest) -> dict | list:
    return await _proxy_json(
        "PUT",
        f"{ORDER_SERVICE_URL}/admin/inventory/{item_name}",
        json=request.model_dump(),
    )


@app.get("/admin/notifications")
async def admin_notifications(unread_only: bool = False, limit: int = 100) -> dict | list:
    return await _proxy_json(
        "GET",
        f"{ORDER_SERVICE_URL}/admin/notifications",
        params={"unread_only": unread_only, "limit": limit},
    )


@app.post("/admin/notifications/{notification_id}/read")
async def admin_mark_notification_read(notification_id: int) -> dict | list:
    return await _proxy_json("POST", f"{ORDER_SERVICE_URL}/admin/notifications/{notification_id}/read")


@app.get("/api/categories")
async def api_categories() -> dict | list:
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/categories")


@app.get("/api/foods")
async def api_foods(category: str | None = None, search: str | None = None) -> dict | list:
    params = {}
    if category: params["category"] = category
    if search: params["search"] = search
    return await _proxy_json("GET", f"{ORDER_SERVICE_URL}/foods", params=params)


async def _proxy_json(
    method: str,
    url: str,
    json: dict | None = None,
    params: dict | None = None,
) -> dict | list:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.request(
                method,
                url,
                json=json,
                params=params,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: str | dict = response.text
        try:
            parsed = response.json()
            detail = parsed.get("detail", parsed)
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from upstream: {exc}") from exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_GATEWAY_PORT)
