"""조건 수정(S7) 경로를 처음부터 끝까지 돌린다.

refine, retrieve, prefilter, score, rerank, compose, guard 를 실제 코드로 돌리고, 바깥에
나가는 것(job 저장소, 임베딩, DB, LLM)만 가짜로 둔다. 보유 제품 단계(B)는 아직 없어
그대로 흘러간다.
"""
import json
import sys
import types

import pytest

from contracts.result import RecommendationResult
from graph.builder import run_scenario
from tests.v2 import test_s2_flow
from tests.v2.test_s2_flow import _BE_예시, 바깥  # noqa: F401

_S7_예시 = _BE_예시.with_name("S7_REFINE.json")

_싼_쿠션 = {
    "p5": {"name": "저가 쿠션", "brand": "A", "category": "base",
           "original_price": 18000, "lowest_price": 18000, "average_score": 4.0, "review_count": 30,
           "feature_json": {"product_type": "쿠션", "finish": "매트"}},
    "p6": {"name": "데일리 쿠션", "brand": "B", "category": "base",
           "original_price": 24000, "lowest_price": 22000, "average_score": 4.3, "review_count": 60,
           "feature_json": {"product_type": "쿠션", "finish": "매트"}},
}


@pytest.fixture
def 수정_바깥(바깥, monkeypatch):
    """이전 job 은 3만원 이하 매트 쿠션 검색이다. 이번 job 은 "더 저렴하게"를 골랐다."""
    for pid, 값 in _싼_쿠션.items():
        monkeypatch.setitem(test_s2_flow._상품, pid, 값)

    이전 = {
        "id": "parent", "scenario": "S2_SEARCH",
        "query_spec": {"request_type": "SEARCH", "category": "base", "target": "SELF",
                       "features": {"product_type": "쿠션", "finish": "매트"},
                       "budget": {"max": 30000}},
        "result": {"items": [{"productId": pid} for pid in ("p1", "p2", "p6")]},
        "state_snapshot": {"candidates": [
            {"product_id": pid, "source": "retrieve", "similarity": s}
            for pid, s in (("p1", 0.92), ("o1", 0.90), ("p2", 0.85), ("p6", 0.80), ("p5", 0.70))
        ]},
    }

    async def load_job(job_id, columns="id"):
        바깥.setdefault("job", []).append(job_id)
        return 이전 if job_id == "parent" else {"id": job_id, "refine_presets": ["CHEAPER"]}

    저장소 = types.SimpleNamespace(load_job=load_job)
    import services
    monkeypatch.setitem(sys.modules, "services.job_store", 저장소)
    monkeypatch.setattr(services, "job_store", 저장소, raising=False)
    return 바깥


def _처음_상태():
    return {
        "job_id": "this", "user_id": "u1", "basis": "SELF", "parent_job_id": "parent",
        "scenario": "S7_REFINE", "raw_query": "더 저렴한 제품으로",
        "query_spec": {"request_type": "REFINE", "target": "SELF"},
        "user_profile": {"skin_type": "OILY", "personal_color": "SPRING_WARM", "skin_concerns": []},
        "weight_prior": None,
    }


@pytest.mark.asyncio
async def test_조건_수정_경로가_이전_후보를_다시_줄_세워_순위_변화를_싣는다(수정_바깥):
    상태 = await run_scenario("S7_REFINE", _처음_상태())
    결과 = 상태["result"]

    assert 상태["trace"] == [
        "refine", "retrieve", "inventory", "prefilter", "score", "rerank", "compose", "guard",
    ]
    RecommendationResult.model_validate(결과)
    assert set(결과) == set(json.loads(_S7_예시.read_text()))

    # 3만원 → 2.4만원. 이전 후보를 다시 줄 세우므로 새로 찾지 않는다
    assert 상태["refine_mode"] == "RERANK"
    assert 수정_바깥["검색"] == []
    assert 결과["query"]["budgetMax"] == 24000
    assert 결과["query"]["raw"] == "더 저렴한 제품으로"

    카드 = {i["productId"]: i for i in 결과["items"]}
    assert set(카드) == {"p5", "p6"}
    assert 카드["p5"]["change"] == "NEW" and 카드["p5"]["rankDelta"] is None
    assert 카드["p6"]["change"] == "UP" and 카드["p6"]["rankDelta"] > 0
