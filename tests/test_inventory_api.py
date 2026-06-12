from datetime import date, timedelta

import httpx
import pytest

from app.api.dependencies import get_inventory_service
from app.main import app
from app.repositories.inventory import InMemoryInventoryRepository
from app.services.inventory_service import InventoryService


@pytest.mark.asyncio
async def test_inventory_preflight_allows_cross_origin() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/inventory",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_inventory_create_and_list() -> None:
    service = InventoryService(repository=InMemoryInventoryRepository())
    app.dependency_overrides[get_inventory_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "name": "Milk",
            "quantity": 2,
            "unit": "bottle",
            "expire_date": (date.today() + timedelta(days=3)).isoformat(),
            "note": "for breakfast",
        }

        create_response = await client.post("/api/inventory", json=payload)
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        list_response = await client.get("/api/inventory")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        detail_response = await client.get(f"/api/inventory/{item_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["name"] == "Milk"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inventory_create_merges_same_item() -> None:
    service = InventoryService(repository=InMemoryInventoryRepository())
    app.dependency_overrides[get_inventory_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "name": "Egg",
            "quantity": 2,
            "unit": "pcs",
            "expire_date": (date.today() + timedelta(days=3)).isoformat(),
        }
        await client.post("/api/inventory", json=payload)
        await client.post("/api/inventory", json={**payload, "quantity": 5})

        list_response = await client.get("/api/inventory")
        data = list_response.json()
        assert list_response.status_code == 200
        assert len(data) == 1
        assert data[0]["quantity"] == 7
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inventory_delete_item() -> None:
    service = InventoryService(repository=InMemoryInventoryRepository())
    app.dependency_overrides[get_inventory_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "name": "Yogurt",
            "quantity": 1,
            "unit": "cup",
            "expire_date": (date.today() + timedelta(days=2)).isoformat(),
        }
        create_response = await client.post("/api/inventory", json=payload)
        item_id = create_response.json()["id"]

        delete_response = await client.delete(f"/api/inventory/{item_id}")
        assert delete_response.status_code == 204

        list_response = await client.get("/api/inventory")
        assert list_response.status_code == 200
        assert list_response.json() == []
    app.dependency_overrides.clear()
