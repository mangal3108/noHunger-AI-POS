from typing import Any, Literal

from pydantic import BaseModel, Field

ToolName = Literal[
    "search_restaurants",
    "get_restaurant_menu",
    "add_item_to_cart",
    "remove_item_from_cart",
    "view_cart",
    "create_order",
    "create_payment_link",
    "track_order",
    "book_table",
    "get_recommendations",
]


class ToolCall(BaseModel):
    tool: ToolName
    input: dict[str, Any] = Field(default_factory=dict)


class SearchRestaurantsInput(BaseModel):
    food_type: str
    location: str | None = None


class GetRestaurantMenuInput(BaseModel):
    restaurant_name: str


class AddItemToCartInput(BaseModel):
    session_id: str
    item_name: str
    quantity: int = Field(ge=1, le=20)
    unit_price: float = Field(ge=0.0)


class RemoveItemFromCartInput(BaseModel):
    session_id: str
    item_name: str
    quantity: int = Field(ge=1, le=20)
