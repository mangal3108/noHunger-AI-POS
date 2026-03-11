from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

from packages.contracts.events import PaymentCompletedEvent
from packages.contracts.order import CreateOrderRequest, OrderItem, OrderRecord


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_INVENTORY: list[dict[str, Any]] = [
    {
        "item_name": "Whopper",
        "unit_price": 199.0,
        "stock_qty": 120,
        "is_available": True,
        "category": "Burgers",
        "description": "Flame-grilled chicken patty with fresh veggies.",
    },
    {
        "item_name": "Veg Whopper",
        "unit_price": 179.0,
        "stock_qty": 120,
        "is_available": True,
        "category": "Burgers",
        "description": "Chargrilled veg patty burger with signature sauce.",
    },
    {
        "item_name": "BK Chicken Whopper",
        "unit_price": 229.0,
        "stock_qty": 100,
        "is_available": True,
        "category": "Burgers",
        "description": "Chicken whopper with extra pickles and smoky mayo.",
    },
    {
        "item_name": "Paneer Tandoori Burger",
        "unit_price": 209.0,
        "stock_qty": 90,
        "is_available": True,
        "category": "Burgers",
        "description": "Indian-spiced paneer patty with tandoori dressing.",
    },
    {
        "item_name": "Crispy Chicken Burger",
        "unit_price": 189.0,
        "stock_qty": 110,
        "is_available": True,
        "category": "Burgers",
        "description": "Crunchy chicken fillet burger with lettuce and mayo.",
    },
    {
        "item_name": "Peri Peri Fries",
        "unit_price": 109.0,
        "stock_qty": 160,
        "is_available": True,
        "category": "Sides",
        "description": "Crispy fries tossed in peri peri seasoning.",
    },
    {
        "item_name": "Classic Fries",
        "unit_price": 89.0,
        "stock_qty": 180,
        "is_available": True,
        "category": "Sides",
        "description": "Salted fries, golden and crunchy.",
    },
    {
        "item_name": "Onion Rings",
        "unit_price": 99.0,
        "stock_qty": 130,
        "is_available": True,
        "category": "Sides",
        "description": "Battered onion rings served with dip.",
    },
    {
        "item_name": "Cheesy Jalapeno Bites",
        "unit_price": 119.0,
        "stock_qty": 95,
        "is_available": True,
        "category": "Sides",
        "description": "Crispy bites with jalapeno and molten cheese.",
    },
    {
        "item_name": "Chicken Nuggets 6pc",
        "unit_price": 149.0,
        "stock_qty": 120,
        "is_available": True,
        "category": "Sides",
        "description": "Golden chicken nuggets served with dip.",
    },
    {
        "item_name": "Chicken Wings 6pc",
        "unit_price": 209.0,
        "stock_qty": 90,
        "is_available": True,
        "category": "Sides",
        "description": "Spicy wings glazed with hot sauce.",
    },
    {
        "item_name": "Coke",
        "unit_price": 79.0,
        "stock_qty": 220,
        "is_available": True,
        "category": "Beverages",
        "description": "Chilled Coke can.",
    },
    {
        "item_name": "Pepsi",
        "unit_price": 79.0,
        "stock_qty": 200,
        "is_available": True,
        "category": "Beverages",
        "description": "Chilled Pepsi can.",
    },
    {
        "item_name": "Lemon Iced Tea",
        "unit_price": 89.0,
        "stock_qty": 150,
        "is_available": True,
        "category": "Beverages",
        "description": "Refreshing lemon iced tea.",
    },
    {
        "item_name": "Cold Coffee",
        "unit_price": 109.0,
        "stock_qty": 120,
        "is_available": True,
        "category": "Beverages",
        "description": "Creamy cold coffee with ice.",
    },
    {
        "item_name": "Chocolate Thick Shake",
        "unit_price": 129.0,
        "stock_qty": 100,
        "is_available": True,
        "category": "Beverages",
        "description": "Rich chocolate shake.",
    },
    {
        "item_name": "Vanilla Soft Serve",
        "unit_price": 69.0,
        "stock_qty": 130,
        "is_available": True,
        "category": "Desserts",
        "description": "Classic vanilla soft serve cup.",
    },
    {
        "item_name": "Choco Lava Cup",
        "unit_price": 99.0,
        "stock_qty": 90,
        "is_available": True,
        "category": "Desserts",
        "description": "Warm chocolate dessert cup.",
    },
    {
        "item_name": "Whopper Combo Meal",
        "unit_price": 319.0,
        "stock_qty": 90,
        "is_available": True,
        "category": "Combos",
        "description": "Whopper + classic fries + coke.",
    },
    {
        "item_name": "Veg Whopper Combo Meal",
        "unit_price": 299.0,
        "stock_qty": 90,
        "is_available": True,
        "category": "Combos",
        "description": "Veg whopper + fries + coke.",
    },
    {
        "item_name": "Family Burger Feast",
        "unit_price": 799.0,
        "stock_qty": 40,
        "is_available": True,
        "category": "Combos",
        "description": "4 burgers + 2 fries + 4 drinks.",
    },
]

MENU_METADATA: dict[str, dict[str, str]] = {
    row["item_name"].lower(): {
        "category": str(row.get("category") or "Chef Specials"),
        "description": str(row.get("description") or ""),
    }
    for row in DEFAULT_INVENTORY
}
MENU_METADATA.setdefault(
    "fries",
    {
        "category": "Sides",
        "description": "Salted fries, golden and crunchy.",
    },
)
MENU_CANONICAL_NAMES: dict[str, str] = {
    row["item_name"].lower(): row["item_name"] for row in DEFAULT_INVENTORY
}


class OrderStore:
    def __init__(self, db_path: str = "data/order_service.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    restaurant_name TEXT NOT NULL,
                    delivery_address TEXT NOT NULL DEFAULT '',
                    payment_method TEXT NOT NULL DEFAULT 'UPI',
                    total_amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    order_status TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(order_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL UNIQUE,
                    unit_price REAL NOT NULL,
                    stock_qty INTEGER NOT NULL,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    order_id TEXT,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "orders", "delivery_address", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "orders", "payment_method", "TEXT NOT NULL DEFAULT 'UPI'")
            self._seed_inventory(conn)
            self._normalize_inventory_names(conn)
            conn.commit()

    def create_order(self, req: CreateOrderRequest) -> OrderRecord:
        now = utc_now_iso()
        order = OrderRecord(
            order_id=str(uuid4()),
            session_id=req.session_id,
            restaurant_name=req.restaurant_name,
            delivery_address=req.delivery_address,
            payment_method=req.payment_method,
            items=req.items,
            total_amount=req.total_amount,
            currency=req.currency,
            order_status="payment_pending",
            payment_status="pending",
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._connection() as conn:
            self._reserve_inventory(conn, order.items)
            conn.execute(
                """
                INSERT INTO orders (
                    order_id, session_id, restaurant_name, delivery_address, payment_method, total_amount, currency,
                    order_status, payment_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_id,
                    order.session_id,
                    order.restaurant_name,
                    order.delivery_address,
                    order.payment_method,
                    order.total_amount,
                    order.currency,
                    order.order_status,
                    order.payment_status,
                    order.created_at,
                    order.updated_at,
                ),
            )
            for item in order.items:
                conn.execute(
                    """
                    INSERT INTO order_items (order_id, item_name, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order.order_id, item.item_name, item.quantity, item.unit_price),
                )
            self._add_low_stock_notifications(conn, order.items)
            self._add_notification(
                conn,
                notification_type="order_received",
                message=f"New order received: {order.order_id} ({len(order.items)} items)",
                order_id=order.order_id,
            )
            conn.commit()
        return order

    def get_order(self, order_id: str) -> OrderRecord | None:
        with self._lock, self._connection() as conn:
            row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not row:
                return None
            return self._row_to_order(conn, row)

    def mark_payment_completed(self, event: PaymentCompletedEvent) -> OrderRecord | None:
        now = utc_now_iso()
        with self._lock, self._connection() as conn:
            exists = conn.execute("SELECT order_id FROM orders WHERE order_id = ?", (event.order_id,)).fetchone()
            if not exists:
                return None
            conn.execute(
                """
                UPDATE orders
                SET order_status = ?, payment_status = ?, updated_at = ?
                WHERE order_id = ?
                """,
                ("confirmed", "paid", now, event.order_id),
            )
            self._add_notification(
                conn,
                notification_type="payment_confirmed",
                message=f"Payment captured for order: {event.order_id}",
                order_id=event.order_id,
            )
            conn.commit()
        return self.get_order(event.order_id)

    def mark_cash_on_delivery(self, order_id: str) -> OrderRecord | None:
        now = utc_now_iso()
        with self._lock, self._connection() as conn:
            exists = conn.execute("SELECT order_id FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if not exists:
                return None
            conn.execute(
                """
                UPDATE orders
                SET order_status = ?, payment_status = ?, payment_method = ?, updated_at = ?
                WHERE order_id = ?
                """,
                ("confirmed", "cod_pending", "COD", now, order_id),
            )
            self._add_notification(
                conn,
                notification_type="cod_confirmed",
                message=f"Cash on Delivery selected for order: {order_id}",
                order_id=order_id,
            )
            conn.commit()
        return self.get_order(order_id)

    def get_menu_items(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT item_name, unit_price, stock_qty, is_available, updated_at
                FROM inventory
                ORDER BY lower(item_name) ASC, datetime(updated_at) DESC
                """
            ).fetchall()
        rows = self._unique_casefold_rows(rows)
        return [
            {
                "item_name": row["item_name"],
                "price": float(row["unit_price"]),
                "stock_qty": int(row["stock_qty"]),
                "is_available": bool(row["is_available"]),
                "category": self._menu_category(row["item_name"]),
                "description": self._menu_description(row["item_name"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
            if bool(row["is_available"]) and int(row["stock_qty"]) > 0
        ]

    def list_inventory(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT item_name, unit_price, stock_qty, is_available, updated_at
                FROM inventory
                ORDER BY lower(item_name) ASC, datetime(updated_at) DESC
                """
            ).fetchall()
        rows = self._unique_casefold_rows(rows)
        return [
            {
                "item_name": row["item_name"],
                "unit_price": float(row["unit_price"]),
                "stock_qty": int(row["stock_qty"]),
                "is_available": bool(row["is_available"]),
                "category": self._menu_category(row["item_name"]),
                "description": self._menu_description(row["item_name"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def upsert_inventory_item(
        self,
        item_name: str,
        unit_price: float,
        stock_qty: int,
        is_available: bool,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        requested_name = item_name.strip()
        if not requested_name:
            raise ValueError("item_name cannot be empty.")
        canonical_name = self._canonical_item_name(requested_name)
        with self._lock, self._connection() as conn:
            existing = conn.execute(
                "SELECT item_name FROM inventory WHERE lower(item_name) = lower(?) LIMIT 1",
                (canonical_name,),
            ).fetchone()
            if existing:
                target_name = str(existing["item_name"])
                conn.execute(
                    """
                    UPDATE inventory
                    SET item_name = ?, unit_price = ?, stock_qty = ?, is_available = ?, updated_at = ?
                    WHERE lower(item_name) = lower(?)
                    """,
                    (canonical_name, unit_price, stock_qty, 1 if is_available else 0, now, target_name),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO inventory (item_name, unit_price, stock_qty, is_available, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (canonical_name, unit_price, stock_qty, 1 if is_available else 0, now),
                )
            conn.commit()
            row = conn.execute(
                "SELECT item_name, unit_price, stock_qty, is_available, updated_at FROM inventory WHERE item_name = ?",
                (canonical_name,),
            ).fetchone()
        return {
            "item_name": row["item_name"],
            "unit_price": float(row["unit_price"]),
            "stock_qty": int(row["stock_qty"]),
            "is_available": bool(row["is_available"]),
            "category": self._menu_category(row["item_name"]),
            "description": self._menu_description(row["item_name"]),
            "updated_at": row["updated_at"],
        }

    def list_orders(self, limit: int = 50) -> list[OrderRecord]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM orders
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_order(conn, row) for row in rows]

    def list_notifications(self, unread_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        query = """
            SELECT id, type, message, order_id, is_read, created_at
            FROM notifications
        """
        params: tuple[Any, ...]
        if unread_only:
            query += " WHERE is_read = 0"
            params = (limit,)
        else:
            params = (limit,)
        query += " ORDER BY datetime(created_at) DESC LIMIT ?"

        with self._lock, self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": int(row["id"]),
                "type": row["type"],
                "message": row["message"],
                "order_id": row["order_id"],
                "is_read": bool(row["is_read"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def mark_notification_read(self, notification_id: int) -> dict[str, Any] | None:
        with self._lock, self._connection() as conn:
            row = conn.execute(
                "SELECT id, type, message, order_id, is_read, created_at FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
            updated = conn.execute(
                "SELECT id, type, message, order_id, is_read, created_at FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
        return {
            "id": int(updated["id"]),
            "type": updated["type"],
            "message": updated["message"],
            "order_id": updated["order_id"],
            "is_read": bool(updated["is_read"]),
            "created_at": updated["created_at"],
        }

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _seed_inventory(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        for row in DEFAULT_INVENTORY:
            item_name = self._canonical_item_name(str(row["item_name"]))
            conn.execute(
                """
                INSERT INTO inventory (item_name, unit_price, stock_qty, is_available, updated_at)
                SELECT ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM inventory WHERE lower(item_name) = lower(?)
                )
                """,
                (
                    item_name,
                    row["unit_price"],
                    row["stock_qty"],
                    1 if row["is_available"] else 0,
                    now,
                    item_name,
                ),
            )

    @staticmethod
    def _canonical_item_name(item_name: str) -> str:
        lowered = item_name.strip().lower()
        return MENU_CANONICAL_NAMES.get(lowered, item_name.strip())

    def _normalize_inventory_names(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT id, item_name, stock_qty FROM inventory").fetchall()
        for row in rows:
            old_id = row["id"]
            old_name = row["item_name"]
            stock = int(row["stock_qty"])
            new_name = self._canonical_item_name(old_name)
            
            if old_name != new_name:
                # Check if new_name already exists
                existing = conn.execute("SELECT id, stock_qty FROM inventory WHERE item_name = ?", (new_name,)).fetchone()
                if existing:
                    # Merge stock and delete old
                    conn.execute("UPDATE inventory SET stock_qty = stock_qty + ? WHERE id = ?", (stock, int(existing["id"])))
                    conn.execute("DELETE FROM inventory WHERE id = ?", (old_id,))
                else:
                    # Just rename
                    conn.execute("UPDATE inventory SET item_name = ? WHERE id = ?", (new_name, old_id))

    @staticmethod
    def _menu_category(item_name: str) -> str:
        meta = MENU_METADATA.get(item_name.lower(), {})
        return str(meta.get("category") or "Chef Specials")

    @staticmethod
    def _menu_description(item_name: str) -> str:
        meta = MENU_METADATA.get(item_name.lower(), {})
        return str(meta.get("description") or "")

    @staticmethod
    def _add_notification(
        conn: sqlite3.Connection,
        notification_type: str,
        message: str,
        order_id: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO notifications (type, message, order_id, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (notification_type, message, order_id, utc_now_iso()),
        )

    @staticmethod
    def _row_to_order(conn: sqlite3.Connection, row: sqlite3.Row) -> OrderRecord:
        item_rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (row["order_id"],)).fetchall()
        items = [
            OrderItem(item_name=r["item_name"], quantity=r["quantity"], unit_price=r["unit_price"])
            for r in item_rows
        ]
        return OrderRecord(
            order_id=row["order_id"],
            session_id=row["session_id"],
            restaurant_name=row["restaurant_name"],
            delivery_address=row["delivery_address"],
            payment_method=row["payment_method"] or "UPI",
            items=items,
            total_amount=row["total_amount"],
            currency=row["currency"],
            order_status=row["order_status"],
            payment_status=row["payment_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _reserve_inventory(conn: sqlite3.Connection, items: list[OrderItem]) -> None:
        for item in items:
            row = conn.execute(
                """
                SELECT item_name, stock_qty, is_available
                FROM inventory
                WHERE lower(item_name) = lower(?)
                """,
                (item.item_name,),
            ).fetchone()
            if not row:
                raise ValueError(f"Item '{item.item_name}' not found in inventory.")
            if not bool(row["is_available"]):
                raise ValueError(f"Item '{item.item_name}' is currently unavailable.")
            if int(row["stock_qty"]) < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{item.item_name}'. Available: {int(row['stock_qty'])}."
                )

        now = utc_now_iso()
        for item in items:
            conn.execute(
                """
                UPDATE inventory
                SET stock_qty = stock_qty - ?, updated_at = ?
                WHERE lower(item_name) = lower(?)
                """,
                (item.quantity, now, item.item_name),
            )

    def _add_low_stock_notifications(self, conn: sqlite3.Connection, items: list[OrderItem]) -> None:
        for item in items:
            row = conn.execute(
                """
                SELECT item_name, stock_qty
                FROM inventory
                WHERE lower(item_name) = lower(?)
                """,
                (item.item_name,),
            ).fetchone()
            if not row:
                continue
            remaining = int(row["stock_qty"])
            if remaining <= 10:
                self._add_notification(
                    conn,
                    notification_type="low_stock",
                    message=f"Low stock alert: {row['item_name']} has only {remaining} left.",
                    order_id=None,
                )
