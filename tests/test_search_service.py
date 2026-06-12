from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas.search import MemorySearchHit
from app.services.search_service import SearchService


def test_merge_hybrid_hits_uses_rrf_and_importance_tiebreak() -> None:
    service = SearchService.__new__(SearchService)
    service._settings = type("S", (), {"memory_hybrid_rrf_k": 60})()

    lexical_hits = [
        MemorySearchHit(
            memory_id="m-1",
            user_id="u",
            memory_type="profile",
            content="A",
            importance=0.5,
            score=3.0,
            lexical_score=3.0,
            vector_score=0.0,
            retrieval_source="lexical",
        ),
        MemorySearchHit(
            memory_id="m-2",
            user_id="u",
            memory_type="profile",
            content="B",
            importance=0.9,
            score=2.0,
            lexical_score=2.0,
            vector_score=0.0,
            retrieval_source="lexical",
        ),
    ]

    vector_hits = [
        MemorySearchHit(
            memory_id="m-2",
            user_id="u",
            memory_type="profile",
            content="B",
            importance=0.9,
            score=4.0,
            lexical_score=0.0,
            vector_score=4.0,
            retrieval_source="vector",
        ),
        MemorySearchHit(
            memory_id="m-3",
            user_id="u",
            memory_type="profile",
            content="C",
            importance=0.1,
            score=3.0,
            lexical_score=0.0,
            vector_score=3.0,
            retrieval_source="vector",
        ),
    ]

    merged = service._merge_hybrid_hits(lexical_hits, vector_hits, top_k=3)

    assert len(merged) == 3
    assert merged[0].memory_id == "m-2"
    assert merged[0].retrieval_source == "hybrid"
    assert merged[0].vector_score == 4.0
    assert merged[0].lexical_score == 2.0

    # m-1 and m-3 each appear in only one list, so both are below m-2.
    assert {merged[1].memory_id, merged[2].memory_id} == {"m-1", "m-3"}


def test_query_rewrite_expands_synonyms() -> None:
    rewritten = SearchService._rewrite_query("我有花生过敏")
    assert "花生" in rewritten
    assert "peanut" in rewritten
    assert "allergy" in rewritten


def test_merge_hybrid_hits_can_boost_recent_items() -> None:
    service = SearchService.__new__(SearchService)
    service._settings = type(
        "S",
        (),
        {
            "memory_hybrid_rrf_k": 60,
            "memory_rerank_weight_relevance": 0.2,
            "memory_rerank_weight_recency": 0.7,
            "memory_rerank_weight_credibility": 0.1,
        },
    )()

    now = datetime.now(timezone.utc)
    lexical_hits = [
        MemorySearchHit(
            memory_id="old-hit",
            user_id="u",
            memory_type="profile",
            content="old",
            importance=0.5,
            score=3.0,
            lexical_score=3.0,
            vector_score=0.0,
            retrieval_source="lexical",
            updated_at=now - timedelta(days=180),
        )
    ]
    vector_hits = [
        MemorySearchHit(
            memory_id="new-hit",
            user_id="u",
            memory_type="profile",
            content="new",
            importance=0.5,
            score=2.9,
            lexical_score=0.0,
            vector_score=2.9,
            retrieval_source="vector",
            updated_at=now,
        )
    ]

    merged = service._merge_hybrid_hits(lexical_hits, vector_hits, top_k=2)
    assert merged[0].memory_id == "new-hit"
