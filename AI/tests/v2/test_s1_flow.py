"""상품 평가(S1) 경로를 처음부터 끝까지 돌린다.

discovery, prefilter, score, alternative, score_lite, collaborative, compose, guard 를 실제
코드로 돌리고, 바깥에 나가는 것(임베딩, DB, LLM)만 가짜로 둔다. 보유 제품 단계(B)는 아직
없어 그대로 흘러간다.
"""
import json
import sys

import pytest

from contracts.result import RecommendationResult
from graph.builder import run_scenario
from tests.v2.test_s2_flow import _BE_예시, _상품, 바깥  # noqa: F401

_S1_예시 = _BE_예시.with_name("S1_EVALUATE.json")


@pytest.fixture
def 평가_바깥(바깥):
    """조건 탐색의 가짜에 기준 상품 벡터와 대체 후보 검색을 더한다.

    기준 상품은 p1 이다. 대체 후보로 o1(보유), p2, p4 가 나온다.
    """
    def get_product_meta_with_vec(pid):
        return {"id": pid, **_상품[pid], "feature_vec": [0.3]}

    def match_alternatives(base_id, count, exclude_ids):
        바깥["대체"] = (base_id, count, exclude_ids)
        return [{"product_id": pid, "similarity": s}
                for pid, s in (("o1", 0.95), ("p2", 0.88), ("p4", 0.70))]

    sys.modules["db.product_reader"].get_product_meta_with_vec = get_product_meta_with_vec
    sys.modules["db.vector_search"].match_alternatives = match_alternatives
    return 바깥


def _처음_상태():
    return {
        "job_id": "j1", "user_id": "u1", "basis": "SELF",
        "scenario": "S1_EVALUATE", "base_product_id": "p1",
        "raw_query": "이 쿠션 나한테 맞아?",
        "query_spec": {"request_type": "EVALUATE", "target": "SELF", "base_product_ref": "p1"},
        "user_profile": {"skin_type": "OILY", "personal_color": "SPRING_WARM", "skin_concerns": []},
        "weight_prior": None,
        # 보유 제품 단계(B)가 아직 없어, 그 단계가 채울 값을 처음부터 넣어 둔다
        "inventory": [{"user_product_id": "up1", "product_id": "o1", "name": "네오 쿠션 21N"}],
    }


@pytest.mark.asyncio
async def test_상품_평가_경로가_끝까지_돌아_계약을_지키는_결과를_만든다(평가_바깥):
    상태 = await run_scenario("S1_EVALUATE", _처음_상태())
    결과 = 상태["result"]

    assert 상태["trace"] == [
        "discovery", "inventory(stub)", "prefilter", "score", "alternative", "score_lite",
        "collaborative", "compose", "guard",
    ]
    RecommendationResult.model_validate(결과)
    assert set(결과) == set(json.loads(_S1_예시.read_text()))

    # 결과 카드는 기준 상품 하나이고, 카테고리는 기준 상품에서 채운다
    assert [i["productId"] for i in 결과["items"]] == ["p1"]
    assert 결과["query"]["category"] == "base"
    assert 결과["query"]["raw"] == "이 쿠션 나한테 맞아?"

    # 기준 상품은 빼고 찾고, 보유 제품(o1)은 대체 후보에서 빠진다
    assert 평가_바깥["대체"] == ("p1", 15, ["p1"])
    대체 = 결과["alternatives"]
    assert "o1" not in [a["productId"] for a in 대체]
    assert 대체, "대체 후보가 비었다"
    for a in 대체:
        assert a["breakdown"][0]["key"] == "similarity"
        assert a["breakdown"][0]["weight"] == 0.0
        assert a["totalScore"] >= 50
    assert 상태["alternatives_dropped_count"] + len(대체) == 2

    assert [s["productId"] for s in 결과["similarUserProducts"]] == ["c1"]
    # 가중치 보정은 기준 상품 채점에서 한 번이다. 대체 후보는 보정하지 않는다
    assert sorted(평가_바깥["LLM"]) == ["compose", "weight"]
