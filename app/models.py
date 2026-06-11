from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_ITEMS_PER_ORDER = 50
MAX_QUANTITY_PER_ITEM = 9999
SKU_PATTERN = r"^[A-Z0-9][A-Z0-9\-]{1,29}$"

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PROCESSING_STOCK = "PROCESSING_STOCK"
    STOCK_RESERVED = "STOCK_RESERVED"
    PROCESSING_TRANSPORT = "PROCESSING_TRANSPORT"
    SENT_TO_TRANSPORT = "SENT_TO_TRANSPORT"
    FAILED = "FAILED"

def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo"))

class StatusTransition(BaseModel):
    status: OrderStatus
    at: datetime

class OrderItem(BaseModel):
    sku: str = Field(min_length=2, max_length=30, pattern=SKU_PATTERN)
    quantity: int = Field(gt=0, le=MAX_QUANTITY_PER_ITEM)
 
    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("sku must be a string")
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("sku must not be blank")
        return normalized

class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    items: list[OrderItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_ORDER)
 
    @field_validator("customer_name", mode="before")
    @classmethod
    def normalize_customer_name(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("customer_name must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("customer_name must not be blank")
        return stripped
 
    @model_validator(mode="after")
    def check_unique_skus(self) -> "OrderCreate":
        skus = [item.sku for item in self.items]
        duplicates = {sku for sku in skus if skus.count(sku) > 1}
        if duplicates:
            raise ValueError(f"duplicate SKUs are not allowed: {', '.join(sorted(duplicates))}")
        return self

class Order(BaseModel):
    id: UUID
    customer_name: str
    items: list[OrderItem]
    status: OrderStatus
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    timeline: list[StatusTransition] = Field(default_factory=list)

class OrderCreatedResponse(BaseModel):
    id: UUID
    status: OrderStatus
    created_at: datetime = Field(default_factory=utcnow)