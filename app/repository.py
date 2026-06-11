from uuid import UUID

from app.models import Order, OrderStatus

class OrderRepository:
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._store[str(order.id)] = order

    def get(self, order_id: UUID) -> Order | None:
        return self._store.get(str(order_id))

    def update_status(self, order_id: UUID, status: OrderStatus) -> None:
        order = self._store.get(str(order_id))
        if order is None:
            raise KeyError(f"Order {order_id} not found")
        self._store[str(order_id)] = order.model_copy(update={"status": status})

order_repository = OrderRepository()