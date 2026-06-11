from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PROCESSING_STOCK = "PROCESSING_STOCK"
    STOCK_RESERVED = "STOCK_RESERVED"
    PROCESSING_TRANSPORT = "PROCESSING_TRANSPORT"
    SENT_TO_TRANSPORT = "SENT_TO_TRANSPORT"
    FAILED = "FAILED"

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

class OrderCreatedResponse(BaseModel):
    id: UUID
    status: OrderStatus