"""홈 루틴(HOME_ROUTINE) 경로를 처음부터 끝까지 돌린다.

alternative(루틴 모드), prefilter, score_lite, compose, guard 를 실제 코드로 돌린다.
보유 제품과 루틴 점검 단계(B)는 아직 없어 가짜 노드로 두고, 바깥(임베딩, DB, LLM)도 가짜로 둔다.
"""
import json
import sys

import pytest

from contracts.result import RecommendationResult
from graph.builder import run_scenario
from tests.v2.test_s2_flow import _BE_예시, _가짜_모듈, 바깥  # noqa: F401

_HOME_ROUTINE_예시 = _BE_예시.with_name("HOME_ROUTINE.json")

_보유 = [
    {"user_product_id": "u1", "product_id": "o1", "name": "네오 쿠션 21N", "category": "base",
     "rating": 2, "opened_at": "2026-05-01", "feature_json": {}, "ingredients": []},
    {"user_product_id": "u2", "product_id": "p4", "name": "럭셔리 쿠션", "category": "base",
     "rating": 5, "opened_at": "2026-04-01", "feature_json": {}, "ingredients": []},
]
_점검 = {
    "pairs": [{"a": {"user_product_id": "u1", "name": "네오 쿠션 21N"},
               "b": {"user_product_id": "u2", "name": "럭셔리 쿠션"},
               "level": "AVOID", "title": "같이 쓰지 마세요", "reason": "자극이 커져요"}],
    "counts": {"ok": 0, "separate": 0, "avoid": 1},
    "schedule": {"morning": ["네오 쿠션 21N"], "evening": [], "tip": None},
    "uncompared_count": 0,
    "checked_user_product_ids": ["u1", "u2"],
}


@pytest.fixture
def 루틴_바깥(바깥, monkeypatch):
    async def inventory(state):
        return {"inventory": _보유}

    async def compatibility(state):
        return {"routine_check": _점검}

    def match_alternatives(base_id, count, exclude_ids):
        바깥["대체"] = (base_id, count, exclude_ids)
        return [{"product_id": pid, "similarity": s}
                for pid, s in (("p1", 0.9), ("p4", 0.88), ("p2", 0.85), ("p3", 0.8))]

    _가짜_모듈(monkeypatch, "graph.nodes.inventory", inventory=inventory)
    _가짜_모듈(monkeypatch, "graph.nodes.compatibility", compatibility=compatibility)
    sys.modules["db.vector_search"].match_alternatives = match_alternatives
    return 바깥


def _처음_상태():
    return {
        "job_id": "home:u1:ROUTINE", "user_id": "u1", "basis": "SELF",
        "scenario": "HOME_ROUTINE", "raw_query": "",
        "query_spec": {"request_type": "SEARCH", "target": "SELF", "use_env": False},
        "user_profile": {"skin_type": "OILY", "personal_color": "SPRING_WARM", "skin_concerns": []},
        "weight_prior": None,
    }


@pytest.mark.asyncio
async def test_홈_루틴_경로가_끝까지_돌아_바꿀_제품과_대체_후보를_낸다(루틴_바깥):
    상태 = await run_scenario("HOME_ROUTINE", _처음_상태())
    결과 = 상태["result"]

    assert 상태["trace"] == [
        "inventory", "compatibility", "alternative", "prefilter", "score_lite", "compose", "guard",
    ]
    RecommendationResult.model_validate(결과)
    assert set(결과) == set(json.loads(_HOME_ROUTINE_예시.read_text()))

    # 횟수가 같아 별점이 낮은 u1 을 바꾸고, 보유 상품을 모두 빼고 찾는다
    assert 루틴_바깥["대체"] == ("o1", 20, ["o1", "p4"])
    대체 = 결과["replacement"]
    assert 대체["replaceTarget"] == {"userProductId": "u1", "name": "네오 쿠션 21N"}
    assert 대체["message"] == "별점이 낮은 쪽을 바꾸는 걸 먼저 권해요"
    ids = [i["productId"] for i in 대체["items"]]
    assert sorted(ids) == ["p1", "p2", "p3"]
    assert all(i["badge"] == "쓰시는 제품 1개와 모두 괜찮아요" for i in 대체["items"])

    assert 결과["counts"] == {"ok": 0, "separate": 0, "avoid": 1}
    assert 결과["checkedUserProductIds"] == ["u1", "u2"]
