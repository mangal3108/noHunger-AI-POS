# Architecture Overview

## System Layers

1. Client chat UI
2. API Gateway
3. AI Agent Service (local-first LLM routing + tool orchestration)
4. Domain microservices (order, payment, etc.)
5. Data layer (Redis + PostgreSQL + Vector DB)

## Local-First LLM Strategy

- Default reasoning/tool selection: local `Mistral`.
- Escalation policy for hard requests or tool failures: `Llama 3` or `GPT-5`.
- Fallback model selection currently implemented as policy stubs in `ai_agent/model_router.py`.

## Session and Memory

- Short-term memory: Redis key `session:{session_id}`.
- Session shape:
  - preferences
  - selected_restaurant
  - cart
  - delivery_address
  - payment_method
  - order_history
- Persistent memory table template provided in `data/migrations/001_base_schema.sql` (`ai_sessions`).

## End-to-End Checkout/Event Pipeline

1. User confirms payment in chat.
2. AI agent creates order via `order-service`.
3. AI agent asks `payment-service` for payment link.
4. User pays externally.
5. Payment gateway sends webhook to `payment-service`.
6. `payment-service` verifies signature and emits `payment.completed`.
7. `order-service` receives event at `/events/payment.completed` and confirms order.

## Next Steps

1. Replace in-memory menu catalog with `restaurant-service` + `menu-service`.
2. Add Qdrant semantic menu retrieval and embedding ingestion.
3. Add notification-service for WhatsApp/SMS/email.
4. Add delivery-service with live ETA and WebSocket updates.
5. Add API gateway auth, rate limiting, and request signing.
