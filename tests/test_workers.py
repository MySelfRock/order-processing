import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from uuid import uuid4

from app.models import Order, OrderItem, OrderStatus, StatusTransition, utcnow
from app.repository import order_repository
from app.stock_service import process_stock, stock_worker
from app.shipping_service import process_transport, shipping_worker


def make_order(**kwargs) -> Order:
    now = utcnow()
    defaults = dict(
        id=uuid4(),
        customer_name="João Silva",
        items=[OrderItem(sku="ABC-123", quantity=1)],
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
        timeline=[StatusTransition(status=OrderStatus.CREATED, at=now)],
    )
    defaults.update(kwargs)
    return Order(**defaults)


class TestProcessStock:
    async def test_transitions_to_stock_reserved(self):
        transport_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)

        await process_stock(order.id, out_queue=transport_q)

        assert order_repository.get(order.id).status == OrderStatus.STOCK_RESERVED

    async def test_enqueues_order_into_transport_queue(self):
        transport_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)

        await process_stock(order.id, out_queue=transport_q)

        assert transport_q.qsize() == 1
        assert await transport_q.get() == order.id

    async def test_timeline_records_processing_and_reserved(self):
        order = make_order()
        order_repository.save(order)

        await process_stock(order.id, out_queue=asyncio.Queue())

        statuses = [t.status for t in order_repository.get(order.id).timeline]
        assert OrderStatus.PROCESSING_STOCK in statuses
        assert OrderStatus.STOCK_RESERVED in statuses


class TestProcessTransport:
    async def test_transitions_to_sent_to_transport(self):
        order = make_order(status=OrderStatus.STOCK_RESERVED)
        order_repository.save(order)

        await process_transport(order.id)

        assert order_repository.get(order.id).status == OrderStatus.SENT_TO_TRANSPORT

    async def test_timeline_records_processing_and_sent(self):
        order = make_order(status=OrderStatus.STOCK_RESERVED)
        order_repository.save(order)

        await process_transport(order.id)

        statuses = [t.status for t in order_repository.get(order.id).timeline]
        assert OrderStatus.PROCESSING_TRANSPORT in statuses
        assert OrderStatus.SENT_TO_TRANSPORT in statuses


class TestFullFlow:
    async def test_order_reaches_sent_to_transport(self):
        stock_q: asyncio.Queue = asyncio.Queue()
        transport_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)
        await stock_q.put(order.id)

        t1 = asyncio.create_task(stock_worker(in_queue=stock_q, out_queue=transport_q))
        t2 = asyncio.create_task(shipping_worker(in_queue=transport_q))
        await asyncio.sleep(2.5)
        t1.cancel()
        t2.cancel()
        await asyncio.gather(t1, t2, return_exceptions=True)

        assert order_repository.get(order.id).status == OrderStatus.SENT_TO_TRANSPORT

    async def test_full_timeline_has_five_transitions(self):
        stock_q: asyncio.Queue = asyncio.Queue()
        transport_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)
        await stock_q.put(order.id)

        t1 = asyncio.create_task(stock_worker(in_queue=stock_q, out_queue=transport_q))
        t2 = asyncio.create_task(shipping_worker(in_queue=transport_q))
        await asyncio.sleep(2.5)
        t1.cancel()
        t2.cancel()
        await asyncio.gather(t1, t2, return_exceptions=True)

        statuses = [t.status for t in order_repository.get(order.id).timeline]
        assert statuses == [
            OrderStatus.CREATED,
            OrderStatus.PROCESSING_STOCK,
            OrderStatus.STOCK_RESERVED,
            OrderStatus.PROCESSING_TRANSPORT,
            OrderStatus.SENT_TO_TRANSPORT,
        ]

    async def test_timestamps_are_monotonically_increasing(self):
        stock_q: asyncio.Queue = asyncio.Queue()
        transport_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)
        await stock_q.put(order.id)

        t1 = asyncio.create_task(stock_worker(in_queue=stock_q, out_queue=transport_q))
        t2 = asyncio.create_task(shipping_worker(in_queue=transport_q))
        await asyncio.sleep(2.5)
        t1.cancel()
        t2.cancel()
        await asyncio.gather(t1, t2, return_exceptions=True)

        timestamps = [t.at for t in order_repository.get(order.id).timeline]
        assert timestamps == sorted(timestamps), "Timestamps devem ser crescentes"


class TestWorkerErrorHandling:
    async def test_stock_worker_sets_failed_on_exception(self):
        stock_q: asyncio.Queue = asyncio.Queue()
        order = make_order()
        order_repository.save(order)
        await stock_q.put(order.id)

        async def boom(order_id, *, out_queue=None):
            raise RuntimeError("Falha simulada")

        with patch("app.stock_service.process_stock", side_effect=boom):
            task = asyncio.create_task(stock_worker(in_queue=stock_q))
            await asyncio.sleep(0.1)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert order_repository.get(order.id).status == OrderStatus.FAILED

    async def test_stock_worker_keeps_running_after_error(self):
        """Worker não deve morrer após uma falha — deve processar o próximo pedido."""
        stock_q: asyncio.Queue = asyncio.Queue()
        transport_q: asyncio.Queue = asyncio.Queue()

        bad_order = make_order()
        good_order = make_order()
        order_repository.save(bad_order)
        order_repository.save(good_order)

        await stock_q.put(bad_order.id)
        await stock_q.put(good_order.id)

        call_count = 0

        async def fail_first_then_succeed(order_id, *, out_queue=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Falha no primeiro pedido")
            await process_stock.__wrapped__(order_id, out_queue=transport_q) \
                if hasattr(process_stock, "__wrapped__") \
                else await _real_process_stock(order_id, out_queue=transport_q)

        from app.stock_service import process_stock as _real_process_stock

        with patch("app.stock_service.process_stock", side_effect=fail_first_then_succeed):
            task = asyncio.create_task(stock_worker(in_queue=stock_q, out_queue=transport_q))
            await asyncio.sleep(1.5)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert order_repository.get(bad_order.id).status == OrderStatus.FAILED
        assert order_repository.get(good_order.id).status == OrderStatus.STOCK_RESERVED
