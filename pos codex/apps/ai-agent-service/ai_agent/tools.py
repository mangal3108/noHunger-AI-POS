from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

import httpx

from packages.contracts.order import CreateOrderRequest, OrderItem


FALLBACK_MENU: list[dict[str, Any]] = [
    {
        "item_name": "Whopper",
        "price": 199.0,
        "stock_qty": 100,
        "is_available": True,
        "category": "Burgers",
        "description": "Flame-grilled chicken patty with fresh veggies.",
    },
    {
        "item_name": "Veg Whopper",
        "price": 179.0,
        "stock_qty": 100,
        "is_available": True,
        "category": "Burgers",
        "description": "Chargrilled veg patty burger with signature sauce.",
    },
    {
        "item_name": "BK Chicken Whopper",
        "price": 229.0,
        "stock_qty": 80,
        "is_available": True,
        "category": "Burgers",
        "description": "Chicken whopper with extra pickles and smoky mayo.",
    },
    {
        "item_name": "Classic Fries",
        "price": 89.0,
        "stock_qty": 140,
        "is_available": True,
        "category": "Sides",
        "description": "Salted fries, golden and crunchy.",
    },
    {
        "item_name": "Coke",
        "price": 79.0,
        "stock_qty": 180,
        "is_available": True,
        "category": "Beverages",
        "description": "Chilled Coke can.",
    },
    {
        "item_name": "Chocolate Thick Shake",
        "price": 129.0,
        "stock_qty": 70,
        "is_available": True,
        "category": "Beverages",
        "description": "Rich chocolate shake.",
    },
]


class ToolExecutor:
    def __init__(self, order_service_url: str, payment_service_url: str, restaurant_name: str = "Bhadawar AI") -> None:
        self.order_service_url = order_service_url
        self.payment_service_url = payment_service_url
        self.restaurant_name = restaurant_name
        self._overview = {
            "name": restaurant_name,
            "rating": 4.7,
            "distance_km": 2.1,
            "cuisines": ["burger", "fast food"],
            "review_summary": "Fast prep, reliable quality, and popular burger combos.",
            "best_for": "quick burger meals",
        }

    async def search_restaurants(self, food_type: str, location: str | None = None) -> list[dict[str, Any]]:
        _ = food_type
        return [
            {
                "name": self._overview["name"],
                "rating": self._overview["rating"],
                "distance_km": self._overview["distance_km"],
                "cuisines": self._overview["cuisines"],
                "review_summary": self._overview["review_summary"],
                "best_for": self._overview["best_for"],
                "location": location or "nearby",
            }
        ]

    async def get_restaurant_menu(self, restaurant_name: str) -> list[dict[str, Any]]:
        if restaurant_name and not self.match_restaurant_name(restaurant_name):
            return []
        menu = await self._fetch_menu_from_order_service()
        if menu:
            return menu
        return [
            {
                "item_name": row["item_name"],
                "price": row["price"],
                "category": row.get("category", "Chef Specials"),
                "description": row.get("description", ""),
            }
            for row in FALLBACK_MENU
            if row["is_available"]
        ]

    async def get_restaurant_overview(self, restaurant_name: str) -> dict[str, Any] | None:
        if restaurant_name and not self.match_restaurant_name(restaurant_name):
            return None
        return dict(self._overview)

    def list_restaurant_names(self) -> list[str]:
        return [self.restaurant_name]

    def match_restaurant_name(self, text: str, allow_fuzzy: bool = True) -> str | None:
        haystack = text.lower()
        canonical = self.restaurant_name
        if canonical.lower() in haystack:
            return canonical

        if not allow_fuzzy:
            return None

        stopwords = {
            "show",
            "menu",
            "review",
            "reviews",
            "rating",
            "best",
            "top",
            "near",
            "nearby",
            "restaurant",
            "restaurants",
            "resturant",
            "resturants",
            "food",
            "want",
            "hungry",
            "craving",
            "pizza",
            "burger",
            "chicken",
            "biryani",
            "sandwich",
            "order",
        }

        words = [w for w in re.findall(r"[a-z0-9]+", haystack) if len(w) > 2 and w not in stopwords]
        phrase_candidates: list[str] = []
        if words:
            phrase_candidates.append(" ".join(words))
            for idx in range(len(words)):
                if idx + 1 < len(words):
                    phrase_candidates.append(f"{words[idx]} {words[idx + 1]}")
                phrase_candidates.append(words[idx])

        best_name = None
        best_score = 0.0
        for phrase in phrase_candidates:
            candidate = canonical.lower()
            score = SequenceMatcher(None, phrase, candidate).ratio()
            if score > best_score:
                best_name = canonical
                best_score = score

        if best_name and best_score >= 0.74:
            return best_name
        return None

    async def add_item_to_cart(
        self, session_state: dict[str, Any], item_name: str, quantity: int, unit_price: float, image: str | None = None
    ) -> dict[str, Any]:
        cart: list[dict[str, Any]] = session_state.setdefault("cart", [])
        for row in cart:
            if row["item_name"].lower() == item_name.lower():
                row["quantity"] += quantity
                row["unit_price"] = unit_price
                if image:
                    row["image"] = image
                return session_state

        cart.append({"item_name": item_name, "quantity": quantity, "unit_price": unit_price, "image": image})
        return session_state

    async def remove_item_from_cart(self, session_state: dict[str, Any], item_name: str, quantity: int) -> dict[str, Any]:
        cart: list[dict[str, Any]] = session_state.setdefault("cart", [])
        target = self._resolve_cart_item(cart, item_name)
        if target:
            target["quantity"] -= quantity
            if target["quantity"] <= 0:
                cart.remove(target)
        return session_state

    async def view_cart(self, session_state: dict[str, Any]) -> dict[str, Any]:
        cart = session_state.get("cart", [])
        total = round(sum(item["quantity"] * item["unit_price"] for item in cart), 2)
        return {"items": cart, "total_amount": total, "currency": "INR"}

    async def create_order(self, session_id: str, session_state: dict[str, Any]) -> dict[str, Any]:
        restaurant_name = self.restaurant_name
        delivery_address = str(session_state.get("delivery_address") or "").strip()
        payment_method = str(session_state.get("payment_method") or "UPI").strip().upper()
        cart = session_state.get("cart", [])
        if not cart:
            raise ValueError("Cart is empty.")
        if not delivery_address:
            raise ValueError("Delivery address is required.")

        items = []
        for item in cart:
            items.append({
                "foodId": "chatbot",
                "name": item["item_name"],
                "price": item["unit_price"],
                "qty": item["quantity"],
                "discount": 0,
                "tax": 0
            })

        # Prepare payload for NoHunger Backend
        payload = {
            "source": "chatbot",
            "user": {
                "name": session_state.get("customer_name") or "Chatbot User",
                "email": session_state.get("customer_email") or f"{session_id}@chatbot.local",
                "phone": session_state.get("customer_phone") or "0000000000",
                "address": session_state.get("delivery_address") or "Chatbot Location"
            },
            "items": items
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{self.order_service_url}/api/orders", json=payload)
            response.raise_for_status()
            res_data = response.json()
            # Map the NoHunger backend response `{ order: { _id, totalAmount } }` to checkout expected dict
            return {
                "order_id": res_data.get("order", {}).get("_id", "unknown"),
                "total_amount": float(res_data.get("order", {}).get("totalAmount", sum(item["price"] * item["qty"] for item in items))),
                "delivery_address": delivery_address
            }

    async def create_payment_link(self, order_id: str, amount: float, method: str = "UPI") -> dict[str, Any]:
        # NoHunger backend doesn't have a payment gateway integration. We will mock a successful link.
        return {
            "status": "success",
            "payment_link": f"http://localhost:5173/payment/{order_id}?amount={amount}&method={method.lower()}"
        }


    async def get_payment_methods(self) -> list[str]:
        fallback = ["UPI", "CARD", "NETBANKING", "WALLET"]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.order_service_url}/payment-methods")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return fallback

        methods = payload.get("methods") if isinstance(payload, dict) else None
        if not isinstance(methods, list):
            return fallback
        normalized = [str(x).upper() for x in methods if str(x).strip()]
        return normalized or fallback

    async def track_order(self, order_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.order_service_url}/orders/{order_id}")
            response.raise_for_status()
            return response.json()

    @staticmethod
    def resolve_menu_item(menu: list[dict[str, Any]], user_item_text: str) -> dict[str, Any] | None:
        query = user_item_text.strip()
        if not query:
            return None

        normalized_query = ToolExecutor._normalize_text(query)
        if not normalized_query:
            return None

        item_norm_map = {item["item_name"]: ToolExecutor._normalize_text(item["item_name"]) for item in menu}

        contains_matches = []
        for item in menu:
            item_norm = item_norm_map[item["item_name"]]
            if item_norm and item_norm in normalized_query:
                contains_matches.append((normalized_query.find(item_norm), -len(item_norm), item))
        if contains_matches:
            contains_matches.sort(key=lambda row: (row[0], row[1]))
            return contains_matches[0][2]

        fragments = ToolExecutor._split_candidate_fragments(query)
        fragments.append(query)

        best_item: dict[str, Any] | None = None
        best_score = 0.0
        for fragment in fragments:
            fragment_norm = ToolExecutor._normalize_text(fragment)
            if not fragment_norm:
                continue

            exact = next((i for i in menu if item_norm_map[i["item_name"]] == fragment_norm), None)
            if exact:
                return exact

            for item in menu:
                item_norm = item_norm_map[item["item_name"]]
                if fragment_norm and fragment_norm in item_norm:
                    return item

                similarity = SequenceMatcher(None, fragment_norm, item_norm).ratio()
                overlap = ToolExecutor._token_overlap(fragment_norm, item_norm)
                score = (0.72 * similarity) + (0.28 * overlap)
                if score > best_score:
                    best_score = score
                    best_item = item

        if best_item and best_score >= 0.58:
            return best_item
        return None

    @staticmethod
    def _split_candidate_fragments(text: str) -> list[str]:
        fragments: list[str] = []
        for part in re.split(r"[\n,;|]+", text):
            candidate = part.strip()
            if candidate:
                fragments.append(candidate)
        for part in re.split(r"\s+-\s+", text):
            candidate = part.strip()
            if candidate:
                fragments.append(candidate)
        return fragments

    async def _fetch_menu_from_order_service(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.order_service_url}/api/foods")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []

        # Handle different response shapes
        data = []
        if isinstance(payload, list):
            data = payload
        elif isinstance(payload, dict) and isinstance(payload.get("value"), list):
            data = payload["value"]
        else:
            return []

        menu: list[dict[str, Any]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            price = row.get("price")
            category_obj = row.get("categoryId")
            category_name = category_obj.get("name") if isinstance(category_obj, dict) else str(category_obj)
            
            if isinstance(name, str) and isinstance(price, (int, float)):
                menu.append(
                    {
                        "item_name": name,
                        "price": float(price),
                        "category": str(category_name or "Chef Specials"),
                        "description": str(row.get("description") or ""),
                        "image": str(row.get("image") or ""),
                    }
                )
        return menu

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = text.lower()
        normalized = normalized.replace("&", " and ")
        normalized = re.sub(r"\b(inr|rs|rupees?)\b", " ", normalized)
        normalized = re.sub(r"\b\d+(?:\.\d+)?\b", " ", normalized)
        normalized = re.sub(r"[^a-z0-9 ]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        a_tokens = {token for token in a.split() if token}
        b_tokens = {token for token in b.split() if token}
        if not a_tokens or not b_tokens:
            return 0.0
        overlap = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        return overlap / union if union else 0.0

    @staticmethod
    def _resolve_cart_item(cart: list[dict[str, Any]], item_name: str) -> dict[str, Any] | None:
        if not cart:
            return None

        query_norm = ToolExecutor._normalize_text(item_name)
        if not query_norm:
            return None

        for row in cart:
            row_norm = ToolExecutor._normalize_text(row["item_name"])
            if row_norm == query_norm or query_norm in row_norm:
                return row

        best = None
        best_score = 0.0
        for row in cart:
            row_norm = ToolExecutor._normalize_text(row["item_name"])
            score = SequenceMatcher(None, query_norm, row_norm).ratio()
            if score > best_score:
                best = row
                best_score = score

        if best and best_score >= 0.58:
            return best
        return None
