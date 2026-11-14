"""조건 탐색(S2) 경로를 처음부터 끝까지 돌린다.

노드마다 따로 테스트해도 노드 사이에 주고받는 상태의 모양이 어긋나면 경로는 깨진다.
retrieve, prefilter, score, collaborative, compose, guard 를 실제 코드로 돌리고, 바깥에
나가는 것(임베딩, DB, LLM)만 가짜로 둔다. 보유 제품 단계(B)는 아직 없어 그대로 흘러간다.
"""
import json
import sys
import types
from pathlib import Path

import pytest

from contracts.result import RecommendationResult
from graph.builder import run_scenario

_BE_예시 = Path(__file__).resolve().parents[3] / "BE/src/test/resources/ai-results/S2_SEARCH.json"

_상품 = {
    "p1": {"name": "베어 워터 쿠션", "brand": "ROMAND", "category": "base",
           "original_price": 32000, "lowest_price": 28000, "average_score": 4.6, "review_count": 120,
           "feature_json": {"product_type": "쿠션", "finish": "매트", "skin_type": "지성"}},
    "p2": {"name": "매트 핏 쿠션", "brand": "CLIO", "category": "base",
           "original_price": 25000, "lowest_price": 25000, "average_score": 4.1, "review_count": 40,
           "feature_json": {"product_type": "쿠션", "finish": "글로우", "skin_type": "건성"}},
    "p3": {"name": "롱웨어 파운데이션", "brand": "ESTEE", "category": "base",
           "original_price": 29000, "lowest_price": 29000, "average_score": 4.8, "review_count": 900,
           "feature_json": {"product_type": "파운데이션", "finish": "매트"}},
    "p4": {"name": "럭셔리 쿠션", "brand": "SULWHASOO", "category": "base",
           "original_price": 60000, "lowest_price": 58000, "average_score": 4.7, "review_count": 300,
           "feature_json": {"product_type": "쿠션"}},
    "o1": {"name": "네오 쿠션 21N", "brand": "LANEIGE", "category": "base",
           "original_price": 30000, "lowest_price": 27000, "average_score": 4.5, "review_count": 500,
           "feature_json": {"product_type": "쿠션", "finish": "매트"}},
    "c1": {"name": "세미매트 쿠션", "brand": "HERA", "category": "base",
           "original_price": 45000, "lowest_price": 45000, "average_score": 4.4, "review_count": 80,
           "feature_json": {"product_type": "쿠션"}},
}


def _가짜_모듈(monkeypatch, 이름: str, **함수):
    모듈 = types.SimpleNamespace(**함수)
    부모_이름, _, 끝 = 이름.rpartition(".")
    부모 = sys.modules.get(부모_이름) or __import__(부모_이름)
    monkeypatch.setitem(sys.modules, 이름, 모듈)
    monkeypatch.setattr(부모, 끝, 모듈, raising=False)
    return 모듈


@pytest.fixture
def 바깥(monkeypatch):
    """임베딩, DB, LLM 을 가짜로 둔다. 부른 것을 남긴다."""
    기록: dict = {"LLM": [], "검색": []}

    class 임베딩:
        @classmethod
        def get(cls):
            return cls()

        def embed(self, text):
            return [0.1, 0.2]

    def match_products(vec, category, count, exclude_ids=None):
        기록["검색"].append((category, count))
        return [{"product_id": pid, "similarity": s}
                for pid, s in (("p1", 0.92), ("o1", 0.90), ("p2", 0.85), ("p3", 0.80), ("p4", 0.75))]

    def match_reviews(vec, pid, count):
        return [{"review_id": "r", "review_text": "", "similarity": 0.8 if pid == "p1" else 0.6}]

    def match_user_contexts(user_id, vec, category, count):
        return []

    def get_products_full(ids):
        return {pid: {"product_id": pid, "image_url": None, **_상품[pid]} for pid in ids if pid in _상품}

    async def run_collaborative(user_id, skin_type, personal_color, exclude_ids=None, top_k=5):
        return [types.SimpleNamespace(id="c1", satisfaction_percent=70)]

    class LLM:
        def __init__(self, role):
            self.role = role

        async def chat_json(self, system, user, **_):
            기록["LLM"].append(self.role)
            if self.role == "compose":
                return {"p1": "지성 피부에 맞고 원하신 매트한 마무리예요"}
            return {"review": 1.2}

    _가짜_모듈(monkeypatch, "services.embedding_service", EmbeddingService=임베딩)
    _가짜_모듈(monkeypatch, "db.vector_search", match_products=match_products,
               match_reviews=match_reviews, match_user_contexts=match_user_contexts)
    _가짜_모듈(monkeypatch, "db.product_reader", get_products_full=get_products_full)
    _가짜_모듈(monkeypatch, "db.trend_reader", get_trending_product_ids=lambda: {"p2"})
    _가짜_모듈(monkeypatch, "agents.collaborative_agent", run_collaborative=run_collaborative)
    _가짜_모듈(monkeypatch, "services.llm",
               LLMRole=types.SimpleNamespace(WEIGHT="weight", COMPOSE="compose"),
               get_llm=lambda role: LLM(role))
    # 성분 부품(B)은 아직 없다
    monkeypatch.setitem(sys.modules, "services.ingredient_store", None)
    monkeypatch.setitem(sys.modules, "rules.compatibility", None)
    return 기록


def _처음_상태():
    return {
        "job_id": "j1", "user_id": "u1", "basis": "SELF",
        "raw_query": "여름 가벼운 매트 쿠션 3만원 이하",
        "query_spec": {
            "request_type": "SEARCH", "category": "base", "target": "SELF",
            "features": {"product_type": "쿠션", "finish": "매트"},
            "conditions": ["여름"], "budget": {"max": 30000}, "confidence": 0.9,
        },
        "user_profile": {"skin_type": "OILY", "personal_color": "SPRING_WARM", "skin_concerns": []},
        "weight_prior": None,
        # 보유 제품 단계(B)가 아직 없어, 그 단계가 채울 값을 처음부터 넣어 둔다
        "inventory": [{"user_product_id": "up1", "product_id": "o1", "name": "네오 쿠션 21N"}],
    }


@pytest.mark.asyncio
async def test_조건_탐색_경로가_끝까지_돌아_계약을_지키는_결과를_만든다(바깥):
    상태 = await run_scenario("S2_SEARCH", _처음_상태())
    결과 = 상태["result"]

    # 모든 단계를 지났고, 아직 없는 것은 보유 제품 단계뿐이다
    assert 상태["trace"] == [
        "retrieve", "inventory(stub)", "prefilter", "score", "collaborative", "compose", "guard",
    ]
    RecommendationResult.model_validate(결과)
    예시 = json.loads(_BE_예시.read_text())
    assert set(결과) == set(예시)

    # 파운데이션(p3)은 제품 종류가, 럭셔리 쿠션(p4)은 예산이 맞지 않아 빠진다
    # 이미 쓰는 쿠션(o1)은 제외 목록으로 간다
    assert [i["productId"] for i in 결과["items"]] == ["p1", "p2"]
    assert [(e["productId"], e["reason"]) for e in 결과["excluded"]] == [("o1", "OWNED")]
    assert 결과["excluded"][0]["name"] == "네오 쿠션 21N"

    첫_카드 = 결과["items"][0]
    assert 첫_카드["name"] == "베어 워터 쿠션" and 첫_카드["price"] == 28000
    assert 첫_카드["reason"] == "지성 피부에 맞고 원하신 매트한 마무리예요"
    assert {b["key"] for b in 첫_카드["breakdown"]} >= {"budget_fit", "review", "query_fit"}
    # 이유를 받지 못한 카드는 규칙 문장이다
    assert 결과["items"][1]["reason"].endswith("점수가 높아요")
    assert [b["type"] for b in 결과["items"][1]["badges"]] == ["TREND"]

    assert [s["productId"] for s in 결과["similarUserProducts"]] == ["c1"]
    assert 결과["query"]["conditions"] == ["쿠션", "매트", "여름"]
    assert 결과["query"]["budgetMax"] == 30000

    # 가중치 보정과 이유 문장, LLM 은 두 번만 부른다
    assert sorted(바깥["LLM"]) == ["compose", "weight"]
    assert 바깥["검색"] == [("base", 60)]
