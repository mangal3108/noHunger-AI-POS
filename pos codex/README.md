# Advanced Conversational AI POS Starter

This repository is a production-style starter for a conversational food ordering POS platform with:

- `ai-agent-service` (chat orchestration + tools)
- `order-service` (order lifecycle + payment event handling)
- `payment-service` (payment link + webhook verification)
- `api-gateway` (single entrypoint proxy)
- Shared contracts under `packages/contracts`
- Base SQL schema under `data/migrations`

## Quick Start

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment template:

```bash
copy .env.example .env
```

4. Start services (different terminals):

```bash
python apps/order-service/main.py
python apps/payment-service/main.py
python apps/ai-agent-service/main.py
python apps/api-gateway/main.py
```

5. Open the basic frontend in your browser:

```text
http://localhost:8000
```

## One-Command Start (PowerShell)

From repo root:

```powershell
.\scripts\run_all.ps1
```

Optional (also starts Docker dependencies):

```powershell
.\scripts\run_all.ps1 -WithInfra
```

To stop all services started by the script:

```powershell
.\scripts\stop_all.ps1
```

Use chat messages like:
- `show menu`
- `add 2 whopper`
- `my address is 22 MG Road, Bangalore`
- `payment options`
- `use cod`
- `pay by card`
- `recommend something under 250`
- `i am vegetarian`
- `what do you remember about me`
- `track order`

Open admin panel:

```text
http://localhost:8000/admin
```

## Service Ports

- API Gateway: `8000`
- AI Agent Service: `8001`
- Order Service: `8002`
- Payment Service: `8003`

## Example Chat Request

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"82933\",\"message\":\"I want burger\"}"
```

## Optional Infra (Redis/Postgres/Qdrant)

If you want optional backing services:

```bash
docker compose up -d
```

## Optional: Local LLM (Ollama)

By default, conversational fallback can use your local model first.

Set these in `.env`:

```env
SINGLE_RESTAURANT_NAME=Codex Kitchen
ENABLE_LOCAL_LLM_CHAT=true
LOCAL_LLM_BASE_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.1:8b
LOCAL_LLM_TIMEOUT_SECONDS=18
```

## Optional: OpenAI-Compatible Replies

The AI agent now supports an OpenAI-compatible chat backend for free-form natural conversation.

Set these in `.env`:

```env
ENABLE_LLM_CHAT=true
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-5-mini
LLM_TIMEOUT_SECONDS=18
LLM_MAX_HISTORY_TURNS=8
```

Notes:
- Local LLM is tried first for free-form chat when enabled.
- If local LLM is unavailable, OpenAI-compatible chat is used if configured.
- If `OPENAI_API_KEY` is empty, the app still works with deterministic fallback responses.
- Tool actions (menu/cart/order/payment/track) remain deterministic and are still handled by backend services.

## Notes

- Local-first model routing is implemented as policy stubs:
  - Local: `Mistral`
  - Optional complex fallback: `Llama 3` / `GPT-5`
- `LangGraph` runner is optional and disabled by default (`ENABLE_LANGGRAPH=false`) to keep startup deterministic.
- Redis is optional. If unavailable, in-memory session storage is used.
- Order service now stores delivery address, inventory, and admin notifications in SQLite.
- Checkout supports multiple modes: `UPI`, `CARD`, `NETBANKING`, `WALLET`, `COD`.
- Chat memory stores user preferences (name/diet/budget/payment/address) for better multi-turn conversations.
- Menu data is structured with categories and descriptions and seeded with a larger catalog.
- Database migration SQL is provided for PostgreSQL in `data/migrations/001_base_schema.sql`.
