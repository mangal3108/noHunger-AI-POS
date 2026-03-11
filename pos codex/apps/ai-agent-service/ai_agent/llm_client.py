from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ChatLLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 18.0,
        enabled: bool = True,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key and self.model)

    async def chat(
        self,
        user_message: str,
        session_state: dict[str, Any],
        history: list[dict[str, str]],
        restaurant_names: list[str],
        menu_text: str | None = None,
    ) -> str | None:
        if not self.is_configured:
            return None

        system_prompt = self._build_system_prompt(session_state, restaurant_names, menu_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for row in history:
            role = row.get("role")
            content = row.get("content", "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 420,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except Exception as exc:
            logger.warning("ChatLLMClient request failed: %s", exc)
            return None

        try:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as exc:
            logger.warning("ChatLLMClient response parse failed: %s", exc)
            return None

        if isinstance(content, str):
            text = content.strip()
            return text or None

        if isinstance(content, list):
            parts: list[str] = []
            for chunk in content:
                if isinstance(chunk, dict):
                    piece = chunk.get("text")
                    if isinstance(piece, str):
                        parts.append(piece)
            joined = "".join(parts).strip()
            return joined or None

        return None

    @staticmethod
    def _build_system_prompt(session_state: dict[str, Any], restaurant_names: list[str], menu_text: str | None = None) -> str:
        selected_restaurant = session_state.get("selected_restaurant")
        payment_method = session_state.get("payment_method")
        delivery_address = session_state.get("delivery_address")
        cart = session_state.get("cart", [])
        cart_items = ", ".join(f"{item['item_name']} x{item['quantity']}" for item in cart[:8]) if cart else "empty"
        restaurants = ", ".join(restaurant_names[:12])
        supported_payments = "UPI, CARD, NETBANKING, WALLET"
        memory = session_state.get("conversation_memory", {})
        memory_lines = []
        if isinstance(memory, dict):
            for key in ("name", "dietary", "spice_preference", "budget_inr", "preferred_payment_method"):
                value = memory.get(key)
                if value:
                    memory_lines.append(f"{key}: {value}")
        memory_summary = "; ".join(memory_lines) if memory_lines else "none"

        menu_context = f"\n\nACTUAL MENU for {selected_restaurant}:\n{menu_text}" if menu_text else ""

        return (
            "You are a conversational food ordering assistant. "
            "Speak naturally, concise, and helpful, like a human concierge. "
            "You can discuss recommendations, explain options, and answer casual chat briefly. "
            "IMPORTANT: When the user asks to order, add, or buy food, you MUST include a special command tag in your response: `[COMMAND: ADD_CART: <qty> | <item_name>]` for each item. "
            "Example user: 'I want 2 whoppers and a coke.'\n"
            "Example response: 'Sure, I can add those. [COMMAND: ADD_CART: 2 | whopper] [COMMAND: ADD_CART: 1 | coke]'\n"
            "If the user wants to remove an item, use `[COMMAND: REMOVE_CART: <qty> | <item_name>]`.\n"
            "If the user wants to set their delivery address, use `[COMMAND: ADDRESS: <address>]`.\n"
            "If the user wants to checkout or pay, use `[COMMAND: CHECKOUT: <payment_method>]`.\n"
            "STRICT RULE: Only recommend and order items that are explicitly listed in the ACTUAL MENU provided below. "
            "Do not invent backend actions or claim an order was placed unless explicitly confirmed by the app. "
            f"Available restaurants: {restaurants}. "
            f"Current selected restaurant: {selected_restaurant or 'none'}. "
            f"Cart snapshot: {cart_items}. "
            f"Payment method: {payment_method or 'not selected'}. "
            f"Supported payments: {supported_payments}. "
            f"Saved user memory: {memory_summary}. "
            f"Delivery address: {delivery_address or 'not saved'}."
            f"{menu_context}"
        )


class LocalOllamaClient:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 18.0,
        enabled: bool = True,
    ) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.model)

    async def chat(
        self,
        user_message: str,
        session_state: dict[str, Any],
        history: list[dict[str, str]],
        restaurant_names: list[str],
        menu_text: str | None = None,
    ) -> str | None:
        if not self.is_configured:
            return None

        system = ChatLLMClient._build_system_prompt(session_state, restaurant_names, menu_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for row in history:
            role = row.get("role")
            content = row.get("content", "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.warning("LocalOllamaClient request to %s failed: %s", self.base_url, exc)
            return None

        try:
            data = response.json()
            content = data.get("message", {}).get("content", "")
        except Exception as exc:
            logger.warning("LocalOllamaClient response parse failed: %s", exc)
            return None
        return content.strip() if isinstance(content, str) and content.strip() else None
