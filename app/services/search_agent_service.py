from __future__ import annotations

from app.schemas.agent_tools import SearchAnswerRequest, SearchAnswerResponse
from app.services.search_service import SearchService


class SearchAgentService:
    def __init__(self, search_service: SearchService | None = None) -> None:
        self._search_service = search_service or SearchService()

    def answer(self, payload: SearchAnswerRequest) -> SearchAnswerResponse:
        try:
            retrieval = self._search_service.search_memory(
                user_id=payload.user_id,
                query=payload.query,
                top_k=3,
                retrieval_mode="hybrid",
            )
        except Exception:
            # Gracefully degrade when Elasticsearch is unavailable.
            return SearchAnswerResponse(
                summary="记忆检索服务暂时不可用，当前返回不含记忆证据的回答。",
                evidence=[],
                retrieval_mode="hybrid",
            )

        evidence = [item.content for item in retrieval.hits[:3]]
        if evidence:
            summary = f"已为你的问题检索到 {len(evidence)} 条相关记忆片段。"
        else:
            summary = "未检索到直接相关的记忆证据，建议补充更多个人记忆信息。"

        return SearchAnswerResponse(summary=summary, evidence=evidence, retrieval_mode=retrieval.retrieval_mode)
