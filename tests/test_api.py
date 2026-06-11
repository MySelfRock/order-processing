import pytest
from httpx import AsyncClient


class TestCreateOrder:
    async def test_returns_201_with_id_and_status(self, client: AsyncClient, valid_payload):
        response = await client.post("/orders", json=valid_payload)
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "CREATED"
        assert "id" in body
        assert "created_at" in body

    async def test_order_persisted_in_repository(self, client: AsyncClient, valid_payload):
        response = await client.post("/orders", json=valid_payload)
        order_id = response.json()["id"]

        get_response = await client.get(f"/orders/{order_id}")
        assert get_response.status_code == 200
        assert get_response.json()["customer_name"] == valid_payload["customer_name"]

    async def test_blank_customer_name_returns_422(self, client: AsyncClient):
        response = await client.post("/orders", json={
            "customer_name": "   ",
            "items": [{"sku": "ABC-123", "quantity": 1}],
        })
        assert response.status_code == 422

    async def test_empty_items_returns_422(self, client: AsyncClient):
        response = await client.post("/orders", json={
            "customer_name": "João Silva",
            "items": [],
        })
        assert response.status_code == 422

    async def test_invalid_quantity_returns_422(self, client: AsyncClient):
        response = await client.post("/orders", json={
            "customer_name": "João Silva",
            "items": [{"sku": "ABC-123", "quantity": 0}],
        })
        assert response.status_code == 422

    async def test_duplicate_skus_returns_422(self, client: AsyncClient):
        response = await client.post("/orders", json={
            "customer_name": "João Silva",
            "items": [
                {"sku": "ABC-123", "quantity": 1},
                {"sku": "ABC-123", "quantity": 2},
            ],
        })
        assert response.status_code == 422


class TestGetOrder:
    async def test_returns_full_order(self, client: AsyncClient, valid_payload):
        create = await client.post("/orders", json=valid_payload)
        order_id = create.json()["id"]

        response = await client.get(f"/orders/{order_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == order_id
        assert body["customer_name"] == "João Silva"
        assert body["items"][0]["sku"] == "ABC-123"
        assert "created_at" in body
        assert "updated_at" in body
        assert "timeline" in body

    async def test_nonexistent_order_returns_404(self, client: AsyncClient):
        response = await client.get("/orders/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    async def test_invalid_uuid_returns_422(self, client: AsyncClient):
        response = await client.get("/orders/not-a-valid-uuid")
        assert response.status_code == 422


class TestGetTimeline:
    async def test_timeline_starts_with_created(self, client: AsyncClient, valid_payload):
        create = await client.post("/orders", json=valid_payload)
        order_id = create.json()["id"]

        response = await client.get(f"/orders/{order_id}/timeline")
        assert response.status_code == 200
        timeline = response.json()
        assert len(timeline) >= 1
        assert timeline[0]["status"] == "CREATED"

    async def test_timeline_has_timestamps(self, client: AsyncClient, valid_payload):
        create = await client.post("/orders", json=valid_payload)
        order_id = create.json()["id"]

        timeline = (await client.get(f"/orders/{order_id}/timeline")).json()
        for entry in timeline:
            assert "at" in entry
            assert entry["at"] is not None

    async def test_timeline_404_for_unknown_order(self, client: AsyncClient):
        response = await client.get("/orders/00000000-0000-0000-0000-000000000000/timeline")
        assert response.status_code == 404
