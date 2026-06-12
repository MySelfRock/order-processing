import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.repository import order_repository
from app import queues


def _drain(q: asyncio.Queue) -> None:
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except asyncio.QueueEmpty:
            break


@pytest.fixture(autouse=True)
def reset_state():
    """Limpa o repositório e as filas entre cada teste."""
    order_repository._store.clear()
    _drain(queues.stock_queue)
    _drain(queues.transport_queue)
    yield
    order_repository._store.clear()
    _drain(queues.stock_queue)
    _drain(queues.transport_queue)


@pytest.fixture
async def client():
    """Cliente HTTP assíncrono apontando para a app FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Content-Type": "application/json"},
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest.fixture
def valid_payload() -> dict:
    return {
        "customer_name": "João Silva",
        "items": [{"sku": "ABC-123", "quantity": 2}],
    }