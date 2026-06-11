import asyncio
import logging
from uuid import UUID
from app.models import OrderStatus
from app.queues import stock_queue, transport_queue
from app.repository import order_repository

logger = logging.getLogger(__name__)

async def process_stock(order_id: UUID) -> None:
    logger.info("Stock: processing order %s", order_id)

    order_repository.update_status(order_id, OrderStatus.PROCESSING_STOCK)
    await asyncio.sleep(1)

    order_repository.update_status(order_id, OrderStatus.STOCK_RESERVED)
    logger.info("Stock: reserved for order %s", order_id)

    await transport_queue.put(order_id)
