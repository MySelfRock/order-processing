import pytest
from pydantic import ValidationError

from app.models import OrderCreate, OrderItem


class TestOrderItem:
    def test_valid_item(self):
        item = OrderItem(sku="ABC-123", quantity=1)
        assert item.sku == "ABC-123"
        assert item.quantity == 1

    def test_sku_is_normalized_to_uppercase(self):
        item = OrderItem(sku="abc-123", quantity=1)
        assert item.sku == "ABC-123"

    def test_sku_strips_surrounding_spaces(self):
        item = OrderItem(sku="  ABC-123  ", quantity=1)
        assert item.sku == "ABC-123"

    def test_sku_blank_raises(self):
        with pytest.raises(ValidationError, match="sku"):
            OrderItem(sku="   ", quantity=1)

    def test_sku_too_short_raises(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="A", quantity=1)

    def test_sku_invalid_characters_raises(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="abc 123", quantity=1)

    def test_quantity_zero_raises(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            OrderItem(sku="ABC-123", quantity=0)

    def test_quantity_negative_raises(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="ABC-123", quantity=-1)

    def test_quantity_above_max_raises(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="ABC-123", quantity=10_000)


class TestOrderCreate:
    def test_valid_order(self):
        order = OrderCreate(
            customer_name="João Silva",
            items=[{"sku": "ABC-123", "quantity": 2}],
        )
        assert order.customer_name == "João Silva"
        assert len(order.items) == 1

    def test_customer_name_stripped(self):
        order = OrderCreate(
            customer_name="  Maria  ",
            items=[{"sku": "XYZ-001", "quantity": 1}],
        )
        assert order.customer_name == "Maria"

    def test_customer_name_blank_raises(self):
        with pytest.raises(ValidationError, match="customer_name"):
            OrderCreate(customer_name="   ", items=[{"sku": "ABC-123", "quantity": 1}])

    def test_customer_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            OrderCreate(customer_name="A", items=[{"sku": "ABC-123", "quantity": 1}])

    def test_empty_items_raises(self):
        with pytest.raises(ValidationError, match="items"):
            OrderCreate(customer_name="João Silva", items=[])

    def test_duplicate_skus_raises(self):
        with pytest.raises(ValidationError, match="duplicate SKUs"):
            OrderCreate(
                customer_name="João Silva",
                items=[
                    {"sku": "ABC-123", "quantity": 1},
                    {"sku": "ABC-123", "quantity": 3},
                ],
            )

    def test_multiple_distinct_skus_allowed(self):
        order = OrderCreate(
            customer_name="João Silva",
            items=[
                {"sku": "ABC-123", "quantity": 1},
                {"sku": "XYZ-999", "quantity": 2},
            ],
        )
        assert len(order.items) == 2
