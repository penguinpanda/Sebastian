from __future__ import annotations

import httpx
import pytest

from app.api.routes.search import get_search_service
from app.main import app


@pytest.mark.asyncio
async def test_create_memory_endpoint() -> None:
    class StubSearchService:
        def index_memory(self, payload):
            assert payload.user_id == "u-1"
            return "m-1", "memory_index", "created"

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/search/memory",
            json={
                "user_id": "u-1",
                "memory_type": "profile",
                "content": "我不吃花生",
                "tags": ["allergy"],
                "importance": 0.8,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["memory_id"] == "m-1"
    assert payload["index"] == "memory_index"
    assert payload["result"] == "created"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_memory_endpoint() -> None:
    class StubSearchService:
        def search_memory(self, user_id: str, query: str, top_k: int, retrieval_mode: str = "hybrid"):
            assert user_id == "u-1"
            assert query == "花生"
            assert top_k == 3
            assert retrieval_mode == "hybrid"
            return {
                "query": query,
                "top_k": top_k,
                "retrieval_mode": retrieval_mode,
                "total": 1,
                "hits": [
                    {
                        "memory_id": "m-1",
                        "user_id": user_id,
                        "memory_type": "profile",
                        "content": "我不吃花生",
                        "tags": ["allergy"],
                        "importance": 0.8,
                        "score": 1.2,
                        "lexical_score": 1.2,
                        "vector_score": 0.0,
                        "retrieval_source": "hybrid",
                        "updated_at": "2026-06-11T00:00:00+00:00",
                    }
                ],
            }

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/search/memory", params={"user_id": "u-1", "query": "花生", "top_k": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["retrieval_mode"] == "hybrid"
    assert payload["hits"][0]["memory_id"] == "m-1"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_memories_endpoint() -> None:
    class StubSearchService:
        def list_memories(self, user_id: str, limit: int = 50):
            assert user_id == "u-1"
            assert limit == 2
            return [
                {
                    "memory_id": "new",
                    "user_id": user_id,
                    "memory_type": "profile",
                    "content": "最新记忆",
                    "tags": ["new"],
                    "importance": 0.8,
                    "score": 0.0,
                    "lexical_score": 0.0,
                    "vector_score": 0.0,
                    "retrieval_source": "lexical",
                    "updated_at": "2026-06-11T10:00:00+00:00",
                },
                {
                    "memory_id": "old",
                    "user_id": user_id,
                    "memory_type": "history",
                    "content": "较早记忆",
                    "tags": [],
                    "importance": 0.5,
                    "score": 0.0,
                    "lexical_score": 0.0,
                    "vector_score": 0.0,
                    "retrieval_source": "lexical",
                    "updated_at": "2026-06-10T10:00:00+00:00",
                },
            ]

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/search/memory/list", params={"user_id": "u-1", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert [item["memory_id"] for item in payload] == ["new", "old"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_memory_endpoint() -> None:
    class StubSearchService:
        def delete_memory(self, user_id: str, memory_id: str):
            assert user_id == "u-1"
            assert memory_id == "m-1"
            return True

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.delete("/api/search/memory/m-1", params={"user_id": "u-1"})

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "memory_id": "m-1"}
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_memory_not_found() -> None:
    class StubSearchService:
        def delete_memory(self, user_id: str, memory_id: str):
            return False

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.delete("/api/search/memory/missing", params={"user_id": "u-1"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Memory not found"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_memory_elasticsearch_unavailable() -> None:
    class StubSearchService:
        def search_memory(self, user_id: str, query: str, top_k: int, retrieval_mode: str = "hybrid"):
            raise RuntimeError("es down")

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/search/memory", params={"user_id": "u-1", "query": "花生"})

    assert response.status_code == 503
    assert "Elasticsearch unavailable" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_memory_with_lexical_mode() -> None:
    class StubSearchService:
        def search_memory(self, user_id: str, query: str, top_k: int, retrieval_mode: str = "hybrid"):
            assert retrieval_mode == "lexical"
            return {
                "query": query,
                "top_k": top_k,
                "retrieval_mode": retrieval_mode,
                "total": 0,
                "hits": [],
            }

    app.dependency_overrides[get_search_service] = lambda: StubSearchService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/search/memory",
            params={"user_id": "u-1", "query": "花生", "retrieval_mode": "lexical"},
        )

    assert response.status_code == 200
    assert response.json()["retrieval_mode"] == "lexical"
    app.dependency_overrides.clear()
