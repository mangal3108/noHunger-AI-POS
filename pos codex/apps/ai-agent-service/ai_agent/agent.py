from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import build_runner
from .llm_client import ChatLLMClient, LocalOllamaClient
from .memory import SessionMemory
from .model_router import ModelRouter
from .settings import settings
from .tools import ToolExecutor


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    used_model: str
    session_state: dict[str, Any]


class ConversationAgent:
    def __init__(self) -> None:
        self.memory = SessionMemory(settings.redis_url)
        self.tools = ToolExecutor(
            settings.order_service_url,
            settings.payment_service_url,
            restaurant_name=settings.single_restaurant_name,
        )
        self.router = ModelRouter(
            local_model=settings.local_model_name,
            remote_model=settings.remote_model_name,
            complexity_threshold=settings.reasoning_complexity_threshold,
        )
        if settings.local_llm_type == "openai_api":
            self.local_llm = ChatLLMClient(
                api_key=settings.local_llm_api_key,
                model=settings.local_llm_model,
                base_url=settings.local_llm_base_url,
                timeout_seconds=settings.local_llm_timeout_seconds,
                enabled=settings.enable_local_llm_chat,
            )
        else:
            self.local_llm = LocalOllamaClient(
                model=settings.local_llm_model,
                base_url=settings.local_llm_base_url,
                timeout_seconds=settings.local_llm_timeout_seconds,
                enabled=settings.enable_local_llm_chat,
            )
        chat_model = settings.openai_chat_model or settings.remote_model_name
        self.chat_llm = ChatLLMClient(
            api_key=settings.openai_api_key,
            model=chat_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            enabled=settings.enable_llm_chat,
        )
        self._runner = build_runner(self._run_turn, enabled=settings.enable_langgraph)
        self._last_model_used = settings.local_model_name

    async def handle_message(self, session_id: str, message: str) -> tuple[str, str, dict[str, Any]]:
        reply = await self._runner(session_id, message)
        session_state = await self.memory.get(session_id)
        self._append_history(session_state, message, reply)
        await self.memory.set(session_id, session_state)
        return reply, self._last_model_used, session_state

    async def _run_turn(self, session_id: str, message: str) -> str:
        session_state = await self.memory.get(session_id)
        self._ensure_memory_shape(session_state)
        raw_text = message.strip()
        text = raw_text.lower()
        self._last_model_used = self.router.choose_model(message)

        if not raw_text:
            return "Tell me what you are craving and I can suggest places instantly."

        previous_memory = dict(session_state.get("conversation_memory", {}))
        self._remember_from_message(session_state, raw_text)
        memory = session_state.get("conversation_memory", {})

        if self._is_profile_update_intent(text) and self._memory_changed(previous_memory, memory):
            await self.memory.set(session_id, session_state)
            return self._profile_update_reply(session_state)

        pending_slot = session_state.get("pending_slot")
        if pending_slot == "delivery_address" and not self._is_address_intent(text):
            guessed_address = self._extract_address(f"my address is {raw_text}")
            if guessed_address:
                session_state["delivery_address"] = guessed_address
                # Continuous Flow: Ask for Name next
                session_state["pending_slot"] = "customer_name"
                await self.memory.set(session_id, session_state)
                return f"Thanks, I saved this delivery address: {guessed_address}. Now, to place your order, what is your name?"
        
        if pending_slot == "customer_name":
            name = raw_text.strip()
            if len(name) < 2:
                return "Please provide a valid name."
            session_state["customer_name"] = name
            
            # Proactive check for next missing field
            if not session_state.get("customer_email"):
                session_state["pending_slot"] = "customer_email"
                await self.memory.set(session_id, session_state)
                return f"Nice to meet you, {name}! Now, what is your email address?"
            elif not session_state.get("customer_phone"):
                session_state["pending_slot"] = "customer_phone"
                await self.memory.set(session_id, session_state)
                return f"Nice to meet you, {name}! What is your mobile number?"
            elif not session_state.get("delivery_address"):
                session_state["pending_slot"] = "delivery_address"
                await self.memory.set(session_id, session_state)
                return f"Nice to meet you, {name}! Where should we deliver this?"
            
            session_state["pending_slot"] = None
            await self.memory.set(session_id, session_state)
            return f"Nice to meet you, {name}! Your profile is ready. Say 'checkout' to finish."
            
        if pending_slot == "customer_email":
            email = raw_text.strip().lower()
            if "@" in email:
                session_state["customer_email"] = email
                if not session_state.get("customer_phone"):
                    session_state["pending_slot"] = "customer_phone"
                    await self.memory.set(session_id, session_state)
                    return "Got it. And finally, your mobile number?"
                elif not session_state.get("delivery_address"):
                    session_state["pending_slot"] = "delivery_address"
                    await self.memory.set(session_id, session_state)
                    return "Got it. And what is your delivery address?"
                
                session_state["pending_slot"] = None
                await self.memory.set(session_id, session_state)
                return "Email saved! Ready to checkout?"
            return "Please provide a valid email address."
            
        if pending_slot == "customer_phone":
            phone = raw_text.strip()
            if len(re.sub(r"\D", "", phone)) >= 10:
                session_state["customer_phone"] = phone
                if not session_state.get("delivery_address"):
                    session_state["pending_slot"] = "delivery_address"
                    await self.memory.set(session_id, session_state)
                    return "Phone saved! Now, where should we deliver this order?"
                
                if not session_state.get("payment_method"):
                    session_state["pending_slot"] = "payment_method"
                    await self.memory.set(session_id, session_state)
                    return "Phone saved! How would you like to pay? (UPI, CARD, or NetBanking)"
                
                session_state["pending_slot"] = None
                await self.memory.set(session_id, session_state)
                return "Phone saved! Say 'checkout' to finish."
            return "Please provide a valid phone number (10+ digits)."
            
        if pending_slot == "payment_method":
            method = self._extract_payment_method(text)
            if method:
                session_state["payment_method"] = method
                session_state["pending_slot"] = None
                await self.memory.set(session_id, session_state)
                return f"Perfect! I've set your payment method to {method}. Ready to place order? Just say 'pay' or 'checkout'."
            return "Please choose a valid payment method (UPI, CARD, or NetBanking)."

        if self._is_emotional_food_query(text):
            return await self._chat_like_reply(raw_text, session_state, session_id)

        if self._is_memory_query_intent(text):
            return self._memory_summary(session_state)

        if self._is_address_intent(text):
            address = self._extract_address(raw_text)
            if not address:
                return "Please share full delivery address. Example: my address is 22 MG Road, Bangalore."
            session_state["delivery_address"] = address
            session_state["pending_slot"] = None
            await self.memory.set(session_id, session_state)
            
            # If identity is complete, go to payment
            if not session_state.get("payment_method"):
                session_state["pending_slot"] = "payment_method"
                await self.memory.set(session_id, session_state)
                return f"Got it, address saved: {address}. Finally, how would you like to pay? (UPI, CARD, or NetBanking)"
            
            return f"Got it, address saved: {address}. Ready to place order? Just say 'pay' or 'checkout'."

        if self._is_payment_options_intent(text):
            methods = await self.tools.get_payment_methods()
            selected = str(session_state.get("payment_method") or "UPI").upper()
            options = ", ".join(methods)
            return (
                f"Available payment methods: {options}.\n"
                f"Current selection: {selected}. You can say 'pay upi', 'pay by card', or 'checkout'."
            )

        if self._is_payment_method_selection_intent(text) and not self._is_checkout_intent(text):
            method = self._extract_payment_method(text)
            if method:
                session_state["payment_method"] = method
                memory = session_state.get("conversation_memory", {})
                if isinstance(memory, dict):
                    memory["preferred_payment_method"] = method
                await self.memory.set(session_id, session_state)
                return f"Payment method updated to {method}. When ready, say 'checkout'."

        if self._is_review_intent(text):
            overview = await self.tools.get_restaurant_overview(settings.single_restaurant_name)
            if overview:
                session_state["selected_restaurant"] = overview["name"]
                await self.memory.set(session_id, session_state)
                return self._format_review_for_restaurant(overview)
            return "I could not find review information right now."

        if self._is_restaurant_search_intent(text):
            return "We are NoHunger AI, your premier dining destination! Say 'show menu' to see what we have to offer."

        if self._is_menu_intent(text):
            restaurant_name = (
                self._extract_restaurant_name(raw_text)
                or session_state.get("selected_restaurant")
                or settings.single_restaurant_name
            )

            menu = await self.tools.get_restaurant_menu(restaurant_name)
            if not menu:
                return f"I could not find menu for {restaurant_name}. Try another restaurant."

            overview = await self.tools.get_restaurant_overview(restaurant_name)
            canonical_name = overview["name"] if overview else restaurant_name
            session_state["selected_restaurant"] = canonical_name
            await self.memory.set(session_id, session_state)
            return self._format_menu(
                canonical_name,
                menu,
                overview,
                session_state.get("conversation_memory"),
            )

        if self._is_add_intent(text) or bool(re.match(r"^add\s+\d+\s+[a-z0-9 ]+$", text)):
            if not session_state.get("selected_restaurant"):
                session_state["selected_restaurant"] = settings.single_restaurant_name

            quantity, item_name = self._parse_cart_command(raw_text, action="add")
            menu = await self.tools.get_restaurant_menu(session_state["selected_restaurant"])
            menu_item = self.tools.resolve_menu_item(menu, item_name)
            if not menu_item:
                return await self._chat_like_reply(raw_text, session_state, session_id)

            session_state = await self.tools.add_item_to_cart(
                session_state=session_state,
                item_name=menu_item["item_name"],
                quantity=quantity,
                unit_price=menu_item["price"],
                image=menu_item.get("image")
            )
            await self.memory.set(session_id, session_state)
            cart = await self.tools.view_cart(session_state)
            return (
                f"Added {quantity} x {menu_item['item_name']} to cart.\n"
                f"Current total: INR {cart['total_amount']:.2f}. You can say 'view cart', 'payment options', or 'checkout'."
            )

        if self._is_remove_intent(text):
            if not session_state.get("cart"):
                return "Your cart is already empty."

            quantity, item_name = self._parse_cart_command(raw_text, action="remove")
            session_state = await self.tools.remove_item_from_cart(session_state, item_name, quantity)
            await self.memory.set(session_id, session_state)
            cart = await self.tools.view_cart(session_state)
            if not cart["items"]:
                return "Done. Your cart is now empty."
            return f"Updated cart. Current total: INR {cart['total_amount']:.2f}."

        if "view cart" in text or text == "cart":
            cart = await self.tools.view_cart(session_state)
            if not cart["items"]:
                return "Your cart is empty."
            lines = [f"- {i['item_name']} x{i['quantity']} = INR {i['quantity'] * i['unit_price']:.2f}" for i in cart["items"]]
            return "Cart:\n" + "\n".join(lines) + f"\nTotal: INR {cart['total_amount']:.2f}"

        if self._is_checkout_intent(text):
            cart = await self.tools.view_cart(session_state)
            if not cart["items"]:
                return "Your cart is empty. Add items before payment."
            # Identity Check: Name -> Email -> Phone -> Address
            if not session_state.get("customer_name"):
                session_state["pending_slot"] = "customer_name"
                await self.memory.set(session_id, session_state)
                return "To place your order, I need some quick details. What is your name?"
            if not session_state.get("customer_email"):
                session_state["pending_slot"] = "customer_email"
                await self.memory.set(session_id, session_state)
                return "Great! What is your email address?"
            if not session_state.get("customer_phone"):
                session_state["pending_slot"] = "customer_phone"
                await self.memory.set(session_id, session_state)
                return "Finally, your phone number?"
            if not str(session_state.get("delivery_address") or "").strip():
                session_state["pending_slot"] = "delivery_address"
                await self.memory.set(session_id, session_state)
                return (
                    "Before checkout, please share delivery address.\n"
                    "Example: my address is 22 MG Road, Bangalore 560001."
                )
            
            # Payment Method Check
            if not session_state.get("payment_method"):
                session_state["pending_slot"] = "payment_method"
                await self.memory.set(session_id, session_state)
                return "Wait, how would you like to pay? (UPI, CARD, or NetBanking)"
            
            method = self._extract_payment_method(text) or str(session_state.get("payment_method") or "UPI").upper()
            session_state["payment_method"] = method
            try:
                order = await self.tools.create_order(session_id, session_state)
                payment = await self.tools.create_payment_link(
                    order_id=order["order_id"],
                    amount=order["total_amount"],
                    method=method,
                )
            except Exception as exc:
                self._last_model_used = self.router.choose_model(message, tool_failed=True)
                raise HTTPException(status_code=502, detail=f"Checkout failed: {exc}") from exc

            session_state["last_order_id"] = order["order_id"]
            session_state["cart"] = []
            await self.memory.set(session_id, session_state)

            return (
                f"Order created: {order['order_id']}\n"
                f"Total: INR {order['total_amount']:.2f}\n"
                f"Delivery: {order['delivery_address']}\n"
                f"Payment method: {method}\n"
                f"Pay here: {payment['payment_link']}\n"
                "Once payment is captured, your order status will update automatically."
            )

        if text.startswith("track") or "order status" in text:
            order_id = self._extract_order_id(text) or session_state.get("last_order_id")
            if not order_id:
                return "Provide an order id. Example: track 8f3a...."
            try:
                details = await self.tools.track_order(order_id)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Tracking failed: {exc}") from exc
            return (
                f"Order {details['order_id']} is {details['order_status']} "
                f"(payment: {details['payment_status']})."
            )

        restaurant_guess = self._extract_restaurant_name(raw_text)
        if restaurant_guess:
            menu = await self.tools.get_restaurant_menu(restaurant_guess)
            if menu:
                session_state["selected_restaurant"] = restaurant_guess
                await self.memory.set(session_id, session_state)
                return self._format_menu(
                    restaurant_guess,
                    menu,
                    await self.tools.get_restaurant_overview(restaurant_guess),
                    session_state.get("conversation_memory"),
                )

        return await self._chat_like_reply(raw_text, session_state, session_id)

    async def _chat_like_reply(self, raw_text: str, session_state: dict[str, Any], session_id: str) -> str:
        history = self._history_for_llm(session_state)
        
        restaurant_name = session_state.get("selected_restaurant") or settings.single_restaurant_name
        menu = await self.tools.get_restaurant_menu(restaurant_name)
        menu_text = ""
        if menu:
            menu_text = "\n".join([f"- {item['item_name']} (INR {item['price']:.2f}): {item.get('description', '')}" for item in menu[:12]])

        if self.local_llm.is_configured:
            local_reply = await self.local_llm.chat(
                user_message=raw_text,
                session_state=session_state,
                history=history,
                restaurant_names=self.tools.list_restaurant_names(),
                menu_text=menu_text
            )
            if local_reply:
                self._last_model_used = self.local_llm.model
                return await self._process_llm_commands(local_reply, session_state, session_id)

        if self.chat_llm.is_configured:
            llm_reply = await self.chat_llm.chat(
                user_message=raw_text,
                session_state=session_state,
                history=history,
                restaurant_names=self.tools.list_restaurant_names(),
                menu_text=menu_text
            )
            if llm_reply:
                self._last_model_used = self.chat_llm.model
                return await self._process_llm_commands(llm_reply, session_state, session_id)

        text = raw_text.lower()
        memory = session_state.get("conversation_memory", {})
        name_prefix = ""
        if isinstance(memory, dict):
            user_name = str(memory.get("name") or "").strip()
            if user_name:
                name_prefix = f"{user_name}, "

        if self._is_greeting(text):
            return (
                f"Hey {name_prefix}I am doing well. I can help you with recommendations, reviews, and full ordering.\n"
                "Tell me what you feel like eating and I will suggest options."
            )

        if self._is_emotional_food_query(text):
            return (
                "Sorry you are having a rough day. Let us pick something comforting.\n"
                "If you want quick comfort: cheesy pizza. If you want filling comfort: biryani.\n"
                "Say 'show pizza places near me' or 'show biryani places near me' and I will shortlist options."
            )

        if self._is_food_comparison_query(text):
            return self._food_comparison_reply(text)

        if self._is_recommendation_intent(text):
            menu = await self.tools.get_restaurant_menu(settings.single_restaurant_name)
            recommendations = self._recommend_from_menu(menu, session_state, text)
            if recommendations:
                rec_lines = [
                    f"- {row['item_name']} (INR {row['price']:.2f})"
                    for row in recommendations[:4]
                ]
                return (
                    f"{name_prefix}based on your preferences and recent context, I suggest:\n"
                    + "\n".join(rec_lines)
                    + "\nTell me what to add."
                )

        if any(token in text for token in ("thank", "thanks", "thx")):
            return "Happy to help. Want me to suggest a quick combo before checkout?"

        if any(token in text for token in ("bye", "goodbye", "see you")):
            return "See you. Come back anytime and I can resume your order."

        if self._is_help_intent(text):
            return self._help_text()

        selected = session_state.get("selected_restaurant")
        if selected:
            return (
                f"We are currently on {selected}. You can ask for reviews, menu advice, cart changes, or checkout.\n"
                "I am having trouble connecting to the AI brain right now to answer complex questions."
            )

        return "I am currently having trouble connecting to the AI brain. Please try again or use the quick action buttons."

    async def _process_llm_commands(self, text: str, session_state: dict[str, Any], session_id: str) -> str:
        add_matches = re.finditer(r"\[COMMAND:\s*ADD_CART:\s*(\d+)\s*\|\s*([^\]]+)\]", text, re.IGNORECASE)
        action_taken = False
        cart_messages = []
        
        for match in add_matches:
            qty = max(1, int(match.group(1)))
            item = match.group(2).strip()
            
            if not session_state.get("selected_restaurant"):
                session_state["selected_restaurant"] = settings.single_restaurant_name
                
            menu = await self.tools.get_restaurant_menu(session_state["selected_restaurant"])
            menu_item = self.tools.resolve_menu_item(menu, item)
            if menu_item:
                session_state = await self.tools.add_item_to_cart(
                    session_state, 
                    menu_item["item_name"], 
                    qty, 
                    menu_item["price"],
                    image=menu_item.get("image")
                )
                action_taken = True
                cart_messages.append(f"Added {qty} x {menu_item['item_name']} to cart.")
            else:
                cart_messages.append(f"Could not find '{item}' in the menu.")
                
        remove_matches = re.finditer(r"\[COMMAND:\s*REMOVE_CART:\s*(\d+)\s*\|\s*([^\]]+)\]", text, re.IGNORECASE)
        for match in remove_matches:
            qty = max(1, int(match.group(1)))
            item = match.group(2).strip()
            session_state = await self.tools.remove_item_from_cart(session_state, item, qty)
            action_taken = True
            cart_messages.append(f"Removed {qty} x {item} from cart.")
            
        address_match = re.search(r"\[COMMAND:\s*ADDRESS:\s*([^\]]+)\]", text, re.IGNORECASE)
        if address_match:
            address = address_match.group(1).strip()
            session_state["delivery_address"] = address
            session_state["pending_slot"] = None
            action_taken = True
            cart_messages.append(f"Delivery address updated to: {address}")
            
        checkout_match = re.search(r"\[COMMAND:\s*CHECKOUT:\s*([^\]]+)\]", text, re.IGNORECASE)
        if checkout_match:
            method = checkout_match.group(1).strip().upper()
            session_state["payment_method"] = method
            cart = await self.tools.view_cart(session_state)
            if not cart["items"]:
                cart_messages.append("Your cart is empty. Add items before payment.")
            elif not str(session_state.get("delivery_address") or "").strip():
                session_state["pending_slot"] = "delivery_address"
                action_taken = True
                cart_messages.append("Before checkout, please share delivery address.")
            else:
                try:
                    order = await self.tools.create_order(session_id, session_state)
                    payment = await self.tools.create_payment_link(order["order_id"], order["total_amount"], method)
                    cart_messages.append(f"Order created: {order['order_id']}. Pay here: {payment['payment_link']}")
                    
                    session_state["last_order_id"] = order["order_id"]
                    session_state["cart"] = []
                    action_taken = True
                except Exception as exc:
                    cart_messages.append(f"Checkout failed: {exc}")

        if action_taken:
            await self.memory.set(session_id, session_state)
            
            # Proactive Flow: Selection -> Identity -> Payment
            # Only trigger proactive identity flow if items were added
            if any("Added" in m for m in cart_messages):
                if not session_state.get("customer_name"):
                    session_state["pending_slot"] = "customer_name"
                    cart_messages.append("\nTo place your order, I need some quick details. What is your name?")
                elif not session_state.get("customer_email"):
                    session_state["pending_slot"] = "customer_email"
                    cart_messages.append("\nGreat! What is your email address?")
                elif not session_state.get("customer_phone"):
                    session_state["pending_slot"] = "customer_phone"
                    cart_messages.append("\nFinally, your phone number?")
                elif not str(session_state.get("delivery_address") or "").strip():
                    session_state["pending_slot"] = "delivery_address"
                    cart_messages.append("\nAnd where should we deliver this? (Share your full address)")
                
                await self.memory.set(session_id, session_state)
            
        clean_text = re.sub(r"\[COMMAND:[^\]]+\]", "", text).strip()
        if cart_messages:
            return clean_text + "\n\n" + "\n".join(cart_messages)
        return clean_text

    @staticmethod
    def _infer_food_type(text: str) -> str | None:
        food_type_map = {
            "burger": ("burger", "burgers", "whopper", "zinger"),
            "pizza": ("pizza", "pizzas", "margherita", "pepperoni"),
            "chicken": ("chicken", "fried chicken", "bucket"),
            "biryani": ("biryani", "dum", "hyderabadi"),
            "sandwich": ("sandwich", "sub", "subway"),
        }
        for food_type, aliases in food_type_map.items():
            if any(alias in text for alias in aliases):
                return food_type
        return None

    def _extract_restaurant_name(self, text: str) -> str | None:
        direct = self.tools.match_restaurant_name(text, allow_fuzzy=False)
        if direct:
            return direct

        lowered = text.lower().strip()
        patterns = [
            r"show (.+?) menu",
            r"menu of (.+)$",
            r"menu for (.+)$",
            r"from (.+)$",
            r"at (.+)$",
        ]
        for pat in patterns:
            match = re.search(pat, lowered)
            if match:
                candidate = match.group(1).strip(" .?!")
                resolved = self.tools.match_restaurant_name(candidate, allow_fuzzy=True)
                if resolved:
                    return resolved
        return None

    @staticmethod
    def _parse_cart_command(text: str, action: str) -> tuple[int, str]:
        lowered = text.lower()
        action_match = re.search(rf"\b{action}\b", lowered)
        tail = text[action_match.end():].strip() if action_match else text.strip()

        quantity = 1
        item_text = tail

        match_qty_first = re.match(r"(\d+)\s+(.+)$", tail)
        if match_qty_first:
            quantity = max(1, int(match_qty_first.group(1)))
            item_text = match_qty_first.group(2)
        else:
            match_qty_last = re.match(r"(.+?)\s+x?\s*(\d+)$", tail)
            if match_qty_last:
                item_text = match_qty_last.group(1)
                quantity = max(1, int(match_qty_last.group(2)))

        # Handle copied menu lines like:
        # "add 2 - Whopper INR 199 - Fries INR 89"
        item_text = re.sub(r"^\s*[-:]+\s*", "", item_text)
        if re.search(r"\s+-\s+", item_text):
            item_text = re.split(r"\s+-\s+", item_text, maxsplit=1)[0]
        item_text = re.sub(
            r"\b(inr|rs|rupees?)\s*\d+(?:\.\d+)?\b",
            " ",
            item_text,
            flags=re.IGNORECASE,
        )

        item_text = re.sub(r"\b(please|pls|to cart|in cart|for me)\b", " ", item_text, flags=re.IGNORECASE)
        item_text = re.sub(r"\s+", " ", item_text).strip(" -:,.")
        return quantity, item_text or "item"

    @staticmethod
    def _extract_order_id(text: str) -> str | None:
        match = re.search(r"track\s+([a-f0-9-]{12,40})", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _format_restaurant_list(food_type: str, restaurants: list[dict[str, Any]]) -> str:
        if len(restaurants) == 1:
            row = restaurants[0]
            cuisines = ", ".join(row.get("cuisines", [])[:2])
            return (
                f"Available restaurant: {row['name']} (rating {row['rating']}, {row['distance_km']} km)\n"
                f"Cuisine: {cuisines}\n"
                f"Why people like it: {row.get('review_summary', '')}\n"
                "Say 'show menu' to start ordering."
            )

        heading = f"Top {food_type} places near you:" if food_type != "food" else "Top restaurants near you:"
        lines = [heading]
        for idx, row in enumerate(restaurants[:5], start=1):
            cuisines = ", ".join(row.get("cuisines", [])[:2])
            best_for = row.get("best_for", "")
            lines.append(
                f"{idx}. {row['name']} | rating {row['rating']} | {row['distance_km']} km | {cuisines}"
            )
            if best_for:
                lines.append(f"   Best for: {best_for}.")
        lines.append("Tell me which one you want and I will open the menu.")
        return "\n".join(lines)

    @staticmethod
    def _format_menu(
        restaurant_name: str,
        menu: list[dict[str, Any]],
        overview: dict[str, Any] | None = None,
        conversation_memory: dict[str, Any] | None = None,
    ) -> str:
        lines = [f"{restaurant_name} menu:"]
        if overview:
            lines.append(
                f"Rating {overview['rating']} | {overview['distance_km']} km | {overview.get('review_summary', '')}"
            )

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in menu:
            category = str(item.get("category") or "Chef Specials")
            grouped.setdefault(category, []).append(item)

        for category in sorted(grouped.keys()):
            lines.append(f"\n{category}:")
            for item in grouped[category][:8]:
                description = str(item.get("description") or "").strip()
                if description:
                    lines.append(f"- {item['item_name']} INR {item['price']:.2f} ({description})")
                else:
                    lines.append(f"- {item['item_name']} INR {item['price']:.2f}")

        if isinstance(conversation_memory, dict):
            budget = conversation_memory.get("budget_inr")
            dietary = conversation_memory.get("dietary")
            if budget:
                lines.append(f"\nI remember your budget is around INR {budget}. I can suggest best picks within that.")
            if dietary:
                lines.append(f"I also remember you prefer {dietary} options.")

        lines.append(
            "I recommend trying our bestseller! To order, just say something like 'add 1 Chicken Biryani'. Then share your address and choose a payment method (UPI, CARD, or NetBanking)."
        )
        return "\n".join(lines)

    @staticmethod
    def _format_review_for_restaurant(overview: dict[str, Any]) -> str:
        cuisines = ", ".join(overview.get("cuisines", []))
        return (
            f"{overview['name']} review snapshot:\n"
            f"Rating: {overview['rating']} | Distance: {overview['distance_km']} km\n"
            f"Cuisines: {cuisines}\n"
            f"Best for: {overview.get('best_for', 'quick meals')}\n"
            f"Summary: {overview.get('review_summary', 'Popular choice in your area.')}"
        )

    @staticmethod
    def _format_review_comparison(food_type: str, restaurants: list[dict[str, Any]]) -> str:
        category = food_type if food_type != "any" else "food"
        lines = [f"Review-wise top picks for {category}:"]
        for idx, row in enumerate(restaurants[:3], start=1):
            lines.append(f"{idx}. {row['name']} (rating {row['rating']}) - {row.get('review_summary', '')}")
        lines.append("Say 'show <restaurant> menu' when you decide.")
        return "\n".join(lines)

    @staticmethod
    def _help_text() -> str:
        return (
            "I can chat naturally and help you choose food, compare reviews, and place the order.\n"
            "Try: 'show menu', 'best item under 250', 'add 2 Veg Whopper', "
            "'my address is 22 MG Road', 'payment options', 'pay by card', 'track order', "
            "or 'what do you remember about me'."
        )

    @classmethod
    def _is_restaurant_search_intent(cls, text: str) -> bool:
        return False  # Single restaurant POS, no search needed

    @staticmethod
    def _is_menu_intent(text: str) -> bool:
        return (
            "menu" in text
            or "what can i order" in text
            or "what do they have" in text
            or "show items" in text
        )

    @staticmethod
    def _is_add_intent(text: str) -> bool:
        return bool(re.search(r"\b(add|include|put)\b", text))

    @staticmethod
    def _is_remove_intent(text: str) -> bool:
        return bool(re.search(r"\b(remove|delete|drop)\b", text))

    @staticmethod
    def _is_review_intent(text: str) -> bool:
        # Simplified for single restaurant
        return "review" in text or "rating" in text or "worth it" in text

    @staticmethod
    def _is_help_intent(text: str) -> bool:
        return any(token in text for token in ("help", "what can you do", "commands", "how to order"))

    @staticmethod
    def _is_checkout_intent(text: str) -> bool:
        return any(
            token in text
            for token in ("checkout", "check out", "place order", "confirm order", "pay", "pay now", "make payment")
        )

    @staticmethod
    def _is_payment_options_intent(text: str) -> bool:
        return any(
            token in text
            for token in (
                "payment options",
                "payment option",
                "payment methods",
                "payment modes",
                "modes of payment",
                "how can i pay",
            )
        )

    @classmethod
    def _is_payment_method_selection_intent(cls, text: str) -> bool:
        if cls._extract_payment_method(text):
            return True
        return any(token in text for token in ("use payment", "payment method", "set payment"))

    @staticmethod
    def _is_greeting(text: str) -> bool:
        greeting_tokens = ("hi", "hello", "hey", "yo")
        if any(re.search(rf"\b{token}\b", text) for token in greeting_tokens):
            return True
        return "how are you" in text

    @staticmethod
    def _is_address_intent(text: str) -> bool:
        return any(
            token in text
            for token in (
                "my address is",
                "address is",
                "delivery address",
                "deliver to",
                "ship to",
                "address:",
            )
        )

    @staticmethod
    def _extract_payment_method(text: str) -> str | None:
        normalized = text.lower()
        mapping: list[tuple[str, str]] = [
            ("cash on delivery", "COD"),
            ("cash on delievery", "COD"),
            ("cash on deliver", "COD"),
            ("cod", "COD"),
            ("cash", "COD"),
            ("upi", "UPI"),
            ("gpay", "UPI"),
            ("phonepe", "UPI"),
            ("paytm", "UPI"),
            ("card", "CARD"),
            ("credit", "CARD"),
            ("debit", "CARD"),
            ("netbanking", "NETBANKING"),
            ("net banking", "NETBANKING"),
            ("wallet", "WALLET"),
        ]
        for token, method in mapping:
            if token in normalized:
                return method
        return None

    @staticmethod
    def _extract_address(raw_text: str) -> str | None:
        patterns = [
            r"my address is\s+(.+)$",
            r"address is\s+(.+)$",
            r"delivery address\s+(.+)$",
            r"deliver to\s+(.+)$",
            r"ship to\s+(.+)$",
            r"address:\s*(.+)$",
        ]
        lowered = raw_text.strip()
        for pat in patterns:
            match = re.search(pat, lowered, flags=re.IGNORECASE)
            if match:
                address = match.group(1).strip(" .")
                if len(address) >= 8:
                    return address
        return None

    @classmethod
    def _is_food_comparison_query(cls, text: str) -> bool:
        food_types = cls._extract_food_types(text)
        has_compare_token = any(token in text for token in ("better", "vs", "versus", "or", "compare"))
        return has_compare_token and len(food_types) >= 2

    @classmethod
    def _food_comparison_reply(cls, text: str) -> str:
        food_types = cls._extract_food_types(text)
        if "pizza" in food_types and "biryani" in food_types:
            if any(token in text for token in ("late night", "night", "light")):
                return (
                    "For late night, pizza is usually the easier pick: lighter to share and less heavy before sleep.\n"
                    "If you want a more filling meal, go for biryani instead."
                )
            if any(token in text for token in ("very hungry", "heavy", "filling", "full")):
                return "Biryani is better if you want a filling meal. Pizza is better for a lighter shared snack."
            return "Pizza is better for sharing; biryani is better for a rich filling meal. Tell me your mood and I will pick one."

        a, b = food_types[0], food_types[1]
        return (
            f"Between {a} and {b}, choose {a} if you want lighter/quick, and {b} if you want richer/filling.\n"
            "If you want, I can shortlist restaurants for either option."
        )

    @staticmethod
    def _is_emotional_food_query(text: str) -> bool:
        emotional_tokens = ("sad", "stressed", "stress", "bad day", "tired", "upset", "low mood")
        has_emotion = any(token in text for token in emotional_tokens)
        has_food_context = any(token in text for token in ("hungry", "food", "eat", "craving", "comfort"))
        return has_emotion and has_food_context

    @classmethod
    def _extract_food_types(cls, text: str) -> list[str]:
        found: list[str] = []
        for food_type, aliases in {
            "burger": ("burger", "burgers", "whopper", "zinger"),
            "pizza": ("pizza", "pizzas", "margherita", "pepperoni"),
            "chicken": ("chicken", "fried chicken", "bucket"),
            "biryani": ("biryani", "dum", "hyderabadi"),
            "sandwich": ("sandwich", "sub", "subway"),
        }.items():
            if any(alias in text for alias in aliases):
                found.append(food_type)
        return found

    @staticmethod
    def _ensure_memory_shape(session_state: dict[str, Any]) -> None:
        memory = session_state.get("conversation_memory")
        if not isinstance(memory, dict):
            memory = {}
        memory.setdefault("name", None)
        memory.setdefault("dietary", None)
        memory.setdefault("spice_preference", None)
        memory.setdefault("budget_inr", None)
        memory.setdefault("preferred_payment_method", None)
        memory.setdefault("last_requested_food_type", None)
        session_state["conversation_memory"] = memory
        session_state.setdefault("pending_slot", None)

    @classmethod
    def _remember_from_message(cls, session_state: dict[str, Any], raw_text: str) -> None:
        memory = session_state.get("conversation_memory", {})
        if not isinstance(memory, dict):
            memory = {}
            session_state["conversation_memory"] = memory

        text = raw_text.lower()

        name_match = re.search(r"\b(my name is|i am called|call me)\s+([a-z][a-z ]{1,24})$", text)
        if name_match:
            possible_name = name_match.group(2).strip().title()
            if 1 <= len(possible_name.split()) <= 3:
                memory["name"] = possible_name

        if any(token in text for token in ("vegetarian", "veg only", "pure veg")):
            memory["dietary"] = "vegetarian"
        elif any(token in text for token in ("non veg", "non-veg", "chicken", "meat")):
            memory["dietary"] = "non-vegetarian"

        if any(token in text for token in ("spicy", "extra spicy", "hot")):
            memory["spice_preference"] = "spicy"
        elif any(token in text for token in ("less spicy", "mild", "not spicy")):
            memory["spice_preference"] = "mild"

        budget_patterns = (
            r"\b(?:under|below)\s*(?:inr|rs)?\s*(\d{2,5})\b",
            r"\b(?:my\s+)?budget\s*(?:is|of|around|about|under|below|upto|up to)?\s*(?:inr|rs)?\s*(\d{2,5})\b",
            r"\b(?:i can spend|i want to spend|spend up to|max(?:imum)?(?: spend)?)\s*(?:inr|rs)?\s*(\d{2,5})\b",
        )
        for pattern in budget_patterns:
            budget_match = re.search(pattern, text)
            if budget_match:
                memory["budget_inr"] = int(budget_match.group(1))
                break

        payment_method = cls._extract_payment_method(text)
        if payment_method:
            memory["preferred_payment_method"] = payment_method

        food_type = cls._infer_food_type(text)
        if food_type:
            memory["last_requested_food_type"] = food_type

    @staticmethod
    def _is_memory_query_intent(text: str) -> bool:
        return any(
            token in text
            for token in (
                "what do you remember",
                "remember about me",
                "my preferences",
                "what is my address",
                "saved details",
            )
        )

    @staticmethod
    def _memory_summary(session_state: dict[str, Any]) -> str:
        memory = session_state.get("conversation_memory", {})
        if not isinstance(memory, dict):
            memory = {}

        parts = []
        if memory.get("name"):
            parts.append(f"name: {memory['name']}")
        if memory.get("dietary"):
            parts.append(f"diet: {memory['dietary']}")
        if memory.get("spice_preference"):
            parts.append(f"spice preference: {memory['spice_preference']}")
        if memory.get("budget_inr"):
            parts.append(f"budget: INR {memory['budget_inr']}")
        if memory.get("preferred_payment_method"):
            parts.append(f"preferred payment: {memory['preferred_payment_method']}")
        if session_state.get("delivery_address"):
            parts.append(f"address: {session_state['delivery_address']}")

        if not parts:
            return "I do not have saved preferences yet. Tell me things like your budget, diet, and address."

        return "Here is what I remember:\n- " + "\n- ".join(parts)

    @staticmethod
    def _is_recommendation_intent(text: str) -> bool:
        return any(
            token in text
            for token in (
                "recommend",
                "suggest",
                "what should i eat",
                "what should i order",
                "best item",
                "give me options",
            )
        )

    @staticmethod
    def _is_profile_update_intent(text: str) -> bool:
        return any(
            token in text
            for token in (
                "my name is",
                "call me",
                "i am called",
                "i am vegetarian",
                "veg only",
                "non veg",
                "budget under",
                "my budget",
                "budget is",
                "budget of",
                "budget around",
                "i can spend",
                "spend up to",
                "i prefer",
            )
        )

    @staticmethod
    def _memory_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
        keys = ("name", "dietary", "spice_preference", "budget_inr", "preferred_payment_method", "last_requested_food_type")
        for key in keys:
            if previous.get(key) != current.get(key):
                return True
        return False

    @staticmethod
    def _profile_update_reply(session_state: dict[str, Any]) -> str:
        memory = session_state.get("conversation_memory", {})
        if not isinstance(memory, dict):
            return "Got it. I saved your preferences."

        parts = []
        if memory.get("name"):
            parts.append(f"name: {memory['name']}")
        if memory.get("dietary"):
            parts.append(f"diet: {memory['dietary']}")
        if memory.get("budget_inr"):
            parts.append(f"budget: INR {memory['budget_inr']}")
        if memory.get("spice_preference"):
            parts.append(f"spice: {memory['spice_preference']}")

        if not parts:
            return "Got it. I saved that preference."

        return "Great, I will remember this: " + ", ".join(parts) + "."

    @classmethod
    def _recommend_from_menu(
        cls,
        menu: list[dict[str, Any]],
        session_state: dict[str, Any],
        text: str,
    ) -> list[dict[str, Any]]:
        if not menu:
            return []

        memory = session_state.get("conversation_memory", {})
        dietary = str(memory.get("dietary") or "").lower() if isinstance(memory, dict) else ""
        budget = memory.get("budget_inr") if isinstance(memory, dict) else None
        food_type = cls._infer_food_type(text) or (memory.get("last_requested_food_type") if isinstance(memory, dict) else None)

        ranked: list[tuple[float, dict[str, Any]]] = []
        for item in menu:
            score = 0.0
            name = str(item.get("item_name", "")).lower()
            category = str(item.get("category", "")).lower()
            description = str(item.get("description", "")).lower()
            price = float(item.get("price", 0.0))

            if food_type and (food_type in name or food_type in category or food_type in description):
                score += 2.2

            if dietary == "vegetarian":
                if any(token in name for token in ("chicken", "meat", "nuggets", "wings")):
                    score -= 3.0
                else:
                    score += 1.2

            if isinstance(budget, int):
                if price <= budget:
                    score += 1.7
                    score += max(0.0, (budget - price) / max(1.0, budget))
                else:
                    score -= min(2.0, (price - budget) / max(1.0, budget))

            if "combo" in name:
                score += 0.3
            if "fries" in name or "shake" in name:
                score += 0.1

            ranked.append((score, item))

        ranked.sort(key=lambda row: row[0], reverse=True)
        return [row[1] for row in ranked[:6]]

    @staticmethod
    def _history_for_llm(session_state: dict[str, Any]) -> list[dict[str, str]]:
        history = session_state.get("conversation_history", [])
        if not isinstance(history, list):
            return []

        max_messages = max(2, settings.llm_max_history_turns * 2)
        trimmed = history[-max_messages:]
        output: list[dict[str, str]] = []
        for row in trimmed:
            if not isinstance(row, dict):
                continue
            role = row.get("role")
            content = row.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                output.append({"role": role, "content": content.strip()})
        return output

    @staticmethod
    def _append_history(session_state: dict[str, Any], user_message: str, assistant_reply: str) -> None:
        history = session_state.get("conversation_history")
        if not isinstance(history, list):
            history = []

        user_text = user_message.strip()
        assistant_text = assistant_reply.strip()

        if user_text:
            history.append({"role": "user", "content": user_text[:1600]})
        if assistant_text:
            history.append({"role": "assistant", "content": assistant_text[:2600]})

        max_messages = max(2, settings.llm_max_history_turns * 2)
        session_state["conversation_history"] = history[-max_messages:]


agent = ConversationAgent()
app = FastAPI(title="AI Agent System", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply, used_model, session_state = await agent.handle_message(request.session_id, request.message)
    return ChatResponse(reply=reply, used_model=used_model, session_state=session_state)
