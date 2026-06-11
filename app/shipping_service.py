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