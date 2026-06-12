from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    memory_type: str = Field(default="profile", min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryCreateResponse(BaseModel):
    memory_id: str
    index: str
    result: str


class MemorySearchHit(BaseModel):
    memory_id: str
    user_id: str
    memory_type: str
    content: str
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.0
    score: float = 0.0
    lexical_score: float = 0.0
    vector_score: float = 0.0
    retrieval_source: Literal["lexical", "vector", "hybrid"] = "lexical"
    updated_at: datetime | None = None


class MemorySearchResponse(BaseModel):
    query: str
    top_k: int
    retrieval_mode: Literal["lexical", "vector", "hybrid"]
    total: int
    hits: list[MemorySearchHit] = Field(default_factory=list)
