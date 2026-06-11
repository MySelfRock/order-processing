from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

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
    sku: str
    quantity: int = Field(gt=0)

class OrderCreate(BaseModel):
    customer_name: str
    items: list[OrderItem]

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