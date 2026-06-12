from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.schemas.search import MemoryCreateRequest, MemoryCreateResponse, MemorySearchHit, MemorySearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search")


def get_search_service() -> SearchService:
    return SearchService()


@router.post("/memory", response_model=MemoryCreateResponse)
def create_memory(
    payload: MemoryCreateRequest,
    service: SearchService = Depends(get_search_service),
) -> MemoryCreateResponse:
    try:
        memory_id, index, result = service.index_memory(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch unavailable: {exc}") from exc

    return MemoryCreateResponse(memory_id=memory_id, index=index, result=result)


@router.get("/memory/list", response_model=list[MemorySearchHit])
def list_memories(
    user_id: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    service: SearchService = Depends(get_search_service),
) -> list[MemorySearchHit]:
    try:
        return service.list_memories(user_id=user_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch unavailable: {exc}") from exc


@router.delete("/memory/{memory_id}", response_model=dict[str, bool | str])
def delete_memory(
    memory_id: str,
    user_id: str = Query(min_length=1, max_length=64),
    service: SearchService = Depends(get_search_service),
) -> dict[str, bool | str]:
    try:
        deleted = service.delete_memory(user_id=user_id, memory_id=memory_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch unavailable: {exc}") from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"deleted": True, "memory_id": memory_id}


@router.get("/memory", response_model=MemorySearchResponse)
def search_memory(
    user_id: str = Query(min_length=1, max_length=64),
    query: str = Query(min_length=1, max_length=200),
    top_k: int | None = Query(default=None, ge=1, le=20),
    retrieval_mode: Literal["lexical", "vector", "hybrid"] = Query(default="hybrid"),
    settings: Settings = Depends(get_settings),
    service: SearchService = Depends(get_search_service),
) -> MemorySearchResponse:
    limit = top_k if top_k is not None else settings.memory_search_top_k_default

    try:
        return service.search_memory(user_id=user_id, query=query, top_k=limit, retrieval_mode=retrieval_mode)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Elasticsearch unavailable: {exc}") from exc
