"""홈 환경(HOME_ENV) 경로를 처음부터 끝까지 돌린다.

coverage, retrieve(홈 모드), prefilter, score_lite, compose, guard 를 실제 코드로 돌린다.
환경 집계와 보유 제품 단계(B)는 아직 없어 가짜 노드로 두고, 바깥(임베딩, DB, LLM)도 가짜로 둔다.
"""
import json

import pytest

from contracts.result import RecommendationResult
from graph.builder import run_scenario
from tests.v2.test_s2_flow import _BE_예시, _가짜_모듈, 바깥  # noqa: F401

_HOME_ENV_예시 = _BE_예시.with_name("HOME_ENV.json")

_필요들 = [
    {"key": "MATTE", "label": "매트 마무리", "basis": "기온 28도 이상 10일",
     "reason_text": "요즘 덥고 습해요", "category": "base",
     "features": {"finish": "매트"}, "conditions": ["매트"]},
    {"key": "GLOW", "label": "촉촉한 마무리", "basis": "습도 40% 미만 18일",
     "reason_text": "요즘 공기가 건조해요", "category": "base",
     "features": {"product_type": "쿠션", "finish": "글로우"}, "conditions": ["촉촉"]},
]
_보유 = [{"user_product_id": "up1", "product_id": "o1", "name": "네오 쿠션 21N",
          "category": "base", "product_type": "쿠션", "price": 27000,
          "feature_json": {"product_type": "쿠션", "finish": "매트"}, "ingredients": []}]


@pytest.fixture
def 홈_바깥(바깥, monkeypatch):
    async def env_history(state):
        return {"env_summary": {"region": "서울", "day_count": 28, "needs": _필요들}}

    async def inventory(state):
        return {"inventory": _보유}

    _가짜_모듈(monkeypatch, "graph.nodes.env_history", env_history=env_history)
    _가짜_모듈(monkeypatch, "graph.nodes.inventory", inventory=inventory)
    return 바깥


def _처음_상태():
    return {
        "job_id": "home:u1:ENV", "user_id": "u1", "basis": "SELF",
        "scenario": "HOME_ENV", "raw_query": "",
        "query_spec": {"request_type": "SEARCH", "target": "SELF", "use_env": True},
        "user_profile": {"skin_type": "OILY", "personal_color": "SPRING_WARM",
                         "skin_concerns": [], "region": "서울"},
        "weight_prior": None,
    }


@pytest.mark.asyncio
async def test_홈_환경_경로가_끝까지_돌아_덮이지_않은_기능을_채울_상품을_낸다(홈_바깥):
    상태 = await run_scenario("HOME_ENV", _처음_상태())
    결과 = 상태["result"]

    assert 상태["trace"] == [
        "env_history", "inventory", "coverage", "retrieve", "prefilter", "score_lite",
        "compose", "guard",
    ]
    RecommendationResult.model_validate(결과)
    assert set(결과) == set(json.loads(_HOME_ENV_예시.read_text()))

    # 보유 쿠션이 매트 마무리를 채우므로 촉촉한 마무리만 찾는다
    assert [(c["key"], c["covered"], c["coveredBy"]) for c in 결과["conditions"]] == [
        ("MATTE", True, "네오 쿠션 21N"), ("GLOW", False, None),
    ]
    assert 홈_바깥["검색"] == [("base", 15)]
    assert 결과["query"]["conditions"] == ["촉촉한 마무리(베이스)"]
    assert 결과["query"]["category"] == "base"

    # 덮이지 않은 기능 하나라 그 기능으로 찾은 상품 중 상위 3개다. 보유 제품은 빠진다
    ids = [i["productId"] for i in 결과["items"]]
    assert len(ids) == 3 and "o1" not in ids
    for 카드 in 결과["items"]:
        assert [b["text"] for b in 카드["badges"] if b["type"] == "ENV"] == ["요즘 공기가 건조해요"]
