from __future__ import annotations

import re
from datetime import datetime, timezone
from math import exp
from typing import Literal
from uuid import uuid4

from app.core.config import get_settings
from app.integrations.elasticsearch_client import get_elasticsearch_client
from app.schemas.search import MemoryCreateRequest, MemorySearchHit, MemorySearchResponse
from app.services.embedding_service import build_embedding_provider


class SearchService:
    """记忆检索服务：负责写入 Elasticsearch，并支持词法、向量和混合检索。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = get_elasticsearch_client()
        self._index = self._settings.elasticsearch_memory_index
        self._embedding_provider = build_embedding_provider(
            self._settings.memory_embedding_provider,
            self._settings.memory_embedding_model,
        )

    def ensure_memory_index(self) -> None:
        """确保 memory_index 存在；首次启动或测试环境会自动创建 mapping。"""
        if self._client.indices.exists(index=self._index):
            return

        self._client.indices.create(
            index=self._index,
            body={
                "mappings": {
                    "properties": {
                        "memory_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "memory_type": {"type": "keyword"},
                        "content": {"type": "text"},
                        "tags": {"type": "keyword"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": self._settings.memory_embedding_dims,
                            "index": True,
                            "similarity": "cosine",
                        },
                        "importance": {"type": "float"},
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},
                    }
                }
            },
        )

    def index_memory(self, payload: MemoryCreateRequest) -> tuple[str, str, str]:
        """将一条用户记忆写入索引，同时生成可用于向量检索的 embedding。"""
        self.ensure_memory_index()
        memory_id = str(uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        embedding = self._embedding_provider.embed(payload.content, self._settings.memory_embedding_dims)

        result = self._client.index(
            index=self._index,
            id=memory_id,
            document={
                "memory_id": memory_id,
                "user_id": payload.user_id,
                "memory_type": payload.memory_type,
                "content": payload.content,
                "tags": payload.tags,
                "embedding": embedding,
                "importance": payload.importance,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
            refresh=True,
        )

        return memory_id, self._index, str(result.get("result", "created"))

    def search_memory(
        self,
        user_id: str,
        query: str,
        top_k: int,
        retrieval_mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    ) -> MemorySearchResponse:
        """按指定模式检索记忆；hybrid 模式会融合词法命中和向量命中。"""
        self.ensure_memory_index()
        normalized_query = self._rewrite_query(query) if self._settings.memory_query_rewrite_enabled else query

        lexical_result = self._client.search(
            index=self._index,
            size=top_k,
            query={
                "bool": {
                    "filter": [{"term": {"user_id": user_id}}],
                    "must": [{"match": {"content": normalized_query}}],
                }
            },
        )
        lexical_hits = self._extract_hits(lexical_result, user_id=user_id, source="lexical")

        vector_hits: list[MemorySearchHit] = []
        if retrieval_mode in {"vector", "hybrid"}:
            query_vector = self._embedding_provider.embed(normalized_query, self._settings.memory_embedding_dims)
            vector_result = self._client.search(
                index=self._index,
                size=top_k,
                query={
                    "script_score": {
                        "query": {"bool": {"filter": [{"term": {"user_id": user_id}}]}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {"query_vector": query_vector},
                        },
                    }
                },
            )
            vector_hits = self._extract_hits(vector_result, user_id=user_id, source="vector")

        if retrieval_mode == "lexical":
            hits = lexical_hits[:top_k]
            total = len(hits)
        elif retrieval_mode == "vector":
            hits = vector_hits[:top_k]
            total = len(hits)
        else:
            hits = self._merge_hybrid_hits(lexical_hits, vector_hits, top_k=top_k)
            total = len(hits)

        return MemorySearchResponse(
            query=normalized_query,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            total=total,
            hits=hits,
        )

    def list_memories(self, user_id: str, limit: int = 50) -> list[MemorySearchHit]:
        """按更新时间倒序列出用户记忆，用于模型记忆页面的默认时间线。"""
        self.ensure_memory_index()
        result = self._client.search(
            index=self._index,
            size=limit,
            query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
            sort=[{"updated_at": {"order": "desc"}}, {"created_at": {"order": "desc"}}],
        )
        return self._extract_hits(result, user_id=user_id, source="lexical")

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """删除指定用户的一条记忆，返回是否实际删除了文档。"""
        self.ensure_memory_index()
        result = self._client.delete_by_query(
            index=self._index,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"user_id": user_id}},
                            {"term": {"memory_id": memory_id}},
                        ]
                    }
                }
            },
            refresh=True,
            conflicts="proceed",
        )
        return int(result.get("deleted", 0)) > 0

    @staticmethod
    def _rewrite_query(query: str) -> str:
        """轻量查询改写：去停用词、加常见同义词，提升中文短查询召回率。"""
        cleaned = query.strip()
        if not cleaned:
            return query

        tokens = [token for token in re.split(r"[^\w\u4e00-\u9fff]+", cleaned.lower()) if token]
        stopwords = {"的", "了", "和", "是", "我", "有", "在", "与", "for", "the", "a", "an", "to"}
        keywords = [token for token in tokens if token not in stopwords]

        synonym_map = {
            "过敏": ["禁忌", "allergy"],
            "禁忌": ["过敏", "avoid"],
            "减脂": ["低卡", "low-calorie"],
            "增肌": ["高蛋白", "high-protein"],
            "花生": ["坚果", "peanut"],
        }

        expanded: list[str] = []
        for token in keywords:
            expanded.append(token)
            expanded.extend(synonym_map.get(token, []))

        # Handle Chinese phrase queries without explicit token boundaries, e.g. "花生过敏".
        # 中文短语常没有空格分词，这里额外做子串匹配，避免“花生过敏”漏掉同义词扩展。
        lower_cleaned = cleaned.lower()
        for key, synonyms in synonym_map.items():
            if key in lower_cleaned:
                expanded.append(key)
                expanded.extend(synonyms)

        dedup: list[str] = []
        seen: set[str] = set()
        for token in expanded:
            if token and token not in seen:
                seen.add(token)
                dedup.append(token)

        return " ".join(dedup) if dedup else cleaned

    @staticmethod
    def _extract_hits(
        result: dict,
        *,
        user_id: str,
        source: Literal["lexical", "vector"],
    ) -> list[MemorySearchHit]:
        """把 Elasticsearch 原始命中转换成前端和 Agent 共用的响应模型。"""
        hits_raw = result.get("hits", {}).get("hits", [])
        records: list[MemorySearchHit] = []
        for hit in hits_raw:
            payload = hit.get("_source", {})
            content = payload.get("content")
            if not content:
                continue

            score = float(hit.get("_score") or 0.0)
            records.append(
                MemorySearchHit(
                    memory_id=payload.get("memory_id", hit.get("_id", "")),
                    user_id=payload.get("user_id", user_id),
                    memory_type=payload.get("memory_type", "profile"),
                    content=content,
                    tags=payload.get("tags", []),
                    importance=float(payload.get("importance", 0.0)),
                    score=score,
                    lexical_score=score if source == "lexical" else 0.0,
                    vector_score=score if source == "vector" else 0.0,
                    retrieval_source=source,
                    updated_at=payload.get("updated_at"),
                )
            )

        return records

    def _merge_hybrid_hits(
        self,
        lexical_hits: list[MemorySearchHit],
        vector_hits: list[MemorySearchHit],
        *,
        top_k: int,
    ) -> list[MemorySearchHit]:
        """使用 RRF 融合词法/向量排名，再叠加新鲜度和重要性做最终排序。"""
        rrf_k = self._settings.memory_hybrid_rrf_k
        relevance_weight = max(0.0, float(getattr(self._settings, "memory_rerank_weight_relevance", 0.7)))
        recency_weight = max(0.0, float(getattr(self._settings, "memory_rerank_weight_recency", 0.2)))
        credibility_weight = max(0.0, float(getattr(self._settings, "memory_rerank_weight_credibility", 0.1)))
        total_weight = relevance_weight + recency_weight + credibility_weight
        if total_weight <= 0:
            relevance_weight, recency_weight, credibility_weight = 1.0, 0.0, 0.0
            total_weight = 1.0

        relevance_weight /= total_weight
        recency_weight /= total_weight
        credibility_weight /= total_weight

        lexical_rank = {item.memory_id: index + 1 for index, item in enumerate(lexical_hits)}
        vector_rank = {item.memory_id: index + 1 for index, item in enumerate(vector_hits)}

        merged: dict[str, MemorySearchHit] = {}
        for item in lexical_hits:
            merged[item.memory_id] = item.model_copy()
        for item in vector_hits:
            if item.memory_id not in merged:
                merged[item.memory_id] = item.model_copy()
            else:
                merged[item.memory_id].vector_score = item.vector_score

        reranked: list[MemorySearchHit] = []
        max_rrf_score = 2.0 / (rrf_k + 1)
        for memory_id, item in merged.items():
            l_rank = lexical_rank.get(memory_id)
            v_rank = vector_rank.get(memory_id)
            relevance_score = 0.0
            if l_rank is not None:
                relevance_score += 1.0 / (rrf_k + l_rank)
            if v_rank is not None:
                relevance_score += 1.0 / (rrf_k + v_rank)

            normalized_relevance = relevance_score / max_rrf_score if max_rrf_score > 0 else 0.0
            recency_score = self._compute_recency_score(item.updated_at)
            credibility_score = min(max(item.importance, 0.0), 1.0)

            final_score = (
                relevance_weight * normalized_relevance
                + recency_weight * recency_score
                + credibility_weight * credibility_score
            )

            item.score = final_score
            item.retrieval_source = "hybrid"
            reranked.append(item)

        reranked.sort(key=lambda item: (item.score, item.importance), reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _compute_recency_score(updated_at: datetime | None) -> float:
        """按更新时间计算 0-1 的新鲜度分数，越新的记忆权重越高。"""
        if updated_at is None:
            return 0.5

        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        age_days = max((now - updated_at).total_seconds() / 86400.0, 0.0)
        return float(exp(-age_days / 30.0))
