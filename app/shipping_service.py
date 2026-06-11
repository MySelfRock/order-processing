import asyncio
import logging

from uuid import UUID
from app.models import OrderStatus
from app.queues import transport_queue
from app.repository import order_repository

logger = logging.getLogger(__name__)

async def process_transport(order_id: UUID) -> None:
    logger.info("Transport: processing order %s", order_id)
 
    order_repository.update_status(order_id, OrderStatus.PROCESSING_TRANSPORT)
    await asyncio.sleep(1)
 
    order_repository.update_status(order_id, OrderStatus.SENT_TO_TRANSPORT)
    logger.info("Transport: dispatched order %s", order_id)
 
 
async def shipping_worker(
    in_queue: asyncio.Queue | None = None,
) -> None:
    logger.info("Shipping worker started")
    source = in_queue if in_queue is not None else transport_queue
    while True:
        order_id: UUID = await source.get()
        try:
            await process_transport(order_id)
        except Exception:
            logger.exception("Transport: error processing order %s", order_id)
            order_repository.update_status(order_id, OrderStatus.FAILED)
        finally:
            source.task_done()