import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException

from app.models import Order, OrderCreate, OrderCreatedResponse, OrderStatus, StatusTransition
from app.queues import stock_queue
from app.repository import order_repository
from app.shipping_service import shipping_worker
from app.stock_service import stock_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(stock_worker(), name="stock-worker"),
        asyncio.create_task(shipping_worker(), name="shipping-worker"),
    ]
    logger.info("Background workers started")
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Background workers stopped")


app = FastAPI(
    title="Order Processing API",
    version="1.0.0",
    lifespan=lifespan,
)

@app.post("/orders", response_model=OrderCreatedResponse, status_code=201)
async def create_order(payload: OrderCreate) -> OrderCreatedResponse:
    order = Order(
        id=uuid4(),
        customer_name=payload.customer_name,
        items=payload.items,
        status=OrderStatus.CREATED,
    )
    order_repository.save(order)
    await stock_queue.put(order.id)
    logger.info("Order created: %s", order.id)
    return OrderCreatedResponse(id=order.id, status=order.status)

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: UUID) -> Order:
    order = order_repository.get(order_id)
    if not order:
        logger.warning("Order not found: %s", order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    logger.info("Order retrieved: %s", order_id)
    return order

@app.get("/orders/{order_id}/timeline", response_model=list[StatusTransition])
async def get_order_timeline(order_id: UUID) -> list[StatusTransition]:
    order = order_repository.get(order_id)
    if order is None:
        logger.warning("Order not found: %s", order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    logger.info("Order timeline retrieved: %s", order_id)
    return order.timeline