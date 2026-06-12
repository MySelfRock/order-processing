import asyncio
import logging
from uuid import UUID
from app.models import OrderStatus
from app import queues as _queues
from app.repository import order_repository

logger = logging.getLogger(__name__)

async def process_stock(
    order_id: UUID,
    *,
    out_queue: asyncio.Queue | None = None,
) -> None:
    logger.info("Stock: processing order %s", order_id)
 
    order_repository.update_status(order_id, OrderStatus.PROCESSING_STOCK)
    await asyncio.sleep(1)
 
    order_repository.update_status(order_id, OrderStatus.STOCK_RESERVED)
    logger.info("Stock: reserved for order %s", order_id)
 
    destination = out_queue if out_queue is not None else _queues.transport_queue
    await destination.put(order_id)

async def stock_worker(
    in_queue: asyncio.Queue | None = None,
    out_queue: asyncio.Queue | None = None,
) -> None:
    logger.info("Stock worker started")
    source = in_queue if in_queue is not None else _queues.stock_queue
    while True:
        order_id: UUID = await source.get()
        try:
            await process_stock(order_id, out_queue=out_queue)
        except Exception:
            logger.exception("Stock: error processing order %s", order_id)
            order_repository.update_status(order_id, OrderStatus.FAILED)
        finally:
            source.task_done()
