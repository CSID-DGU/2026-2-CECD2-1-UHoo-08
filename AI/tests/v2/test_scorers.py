"""점수 항목이 지켜야 할 성질.

None 은 0점이 아니다. 따질 수 없는 상품에 0점을 주면 그 상품만 부당하게
깎이고, 따지지 않는 요청에서 0점을 주면 모든 후보가 같이 깎인다.
"""
import sys
import types

import pytest

from contracts.query_spec import Budget, QuerySpec, RequestType, Target
from contracts.score import ScoreContext
from scorers.budget_fit import budget_fit
from scorers.personalization import personalization
from scorers.popularity import popularity
from scorers.price_value import price_value
from scorers.query_fit import query_fit
from scorers.review import review


def _맥락(**덮어쓰기) -> ScoreContext:
    스펙 = dict(request_type=RequestType.SEARCH)
    스펙.update(덮어쓰기.pop("spec", {}))
    return ScoreContext(job_id="j1", user_id="u1", query_spec=QuerySpec(**스펙), **덮어쓰기)


def _상품(pid="p1", **값) -> dict:
    return {"product_id": pid, "category": "base", **값}


# 예산 적합

@pytest.mark.asyncio
@pytest.mark.parametrize("가격, 기대", [
    (20000, 100),   # 상한 아래
    (30000, 100),   # 정확히 상한
    (37500, 50),    # 상한과 1.5배 사이
    (45000, 0),     # 정확히 1.5배
    (60000, 0),     # 그 위
])
async def test_예산_상한이_있으면_상한과_비교한다(가격, 기대):
    결과 = await budget_fit([_상품(price=가격)], _맥락(spec={"budget": Budget(max=30000)}))
    assert 결과["p1"] == 기대


@pytest.mark.asyncio
@pytest.mark.parametrize("가격, 기대", [
    (7000, 100),    # 중앙값의 0.7배
    (11000, 60),    # 0.7배와 1.5배 사이 (1.1배)
    (15000, 20),    # 1.5배
    (30000, 20),    # 그 위는 바닥 점수
])
async def test_예산이_없으면_카테고리_중앙값과_비교한다(가격, 기대):
    맥락 = _맥락(category_stats={"base": {"median_price": 10000}})
    결과 = await budget_fit([_상품(price=가격)], 맥락)
    assert 결과["p1"] == pytest.approx(기대)


@pytest.mark.asyncio
async def test_가격이나_비교할_기준이_없으면_예산_점수는_None이다():
    상품들 = [_상품("p1", price=None), _상품("p2", price=10000, category="lip")]
    결과 = await budget_fit(상품들, _맥락(category_stats={"base": {"median_price": 10000}}))
    assert 결과 == {"p1": None, "p2": None}


# 할인율

@pytest.mark.asyncio
async def test_할인율로_점수를_낸다():
    상품들 = [
        _상품("p1", lowest_price=30000, original_price=30000),
        _상품("p2", lowest_price=24000, original_price=30000),
        _상품("p3", lowest_price=12000, original_price=30000),
        _상품("p4", lowest_price=None, original_price=30000),
        _상품("p5", lowest_price=10000, original_price=None),
    ]
    결과 = await price_value(상품들, _맥락())
    assert 결과 == {"p1": 50, "p2": 70, "p3": 100, "p4": None, "p5": None}


# 후기 일치

@pytest.fixture
def 후기(monkeypatch):
    """후기 검색을 가짜로 둔다. 상품별 유사도 목록을 받는다."""
    def 세우기(상품별: dict):
        불린: list[str] = []

        def match_reviews(벡터, pid, 개수):
            불린.append(pid)
            return [{"review_id": "r", "review_text": "", "similarity": s}
                    for s in 상품별.get(pid, [])]

        모듈 = types.SimpleNamespace(match_reviews=match_reviews)
        import db
        monkeypatch.setitem(sys.modules, "db.vector_search", 모듈)
        monkeypatch.setattr(db, "vector_search", 모듈, raising=False)
        return 불린

    return 세우기


@pytest.mark.asyncio
async def test_후기_유사도_평균으로_점수를_낸다(후기):
    후기({"p1": [0.8, 0.6], "p2": [1.4]})
    결과 = await review([_상품("p1"), _상품("p2"), _상품("p3")], _맥락(intent_vector=[0.1]))
    # 1 을 넘는 유사도는 1 로 자른다. 후기가 없는 상품은 None
    assert 결과 == {"p1": pytest.approx(70), "p2": 100, "p3": None}


@pytest.mark.asyncio
async def test_질의_벡터가_없으면_후기를_찾지_않는다(후기):
    불린 = 후기({"p1": [0.8]})
    결과 = await review([_상품("p1")], _맥락())
    assert 결과 == {"p1": None}
    assert 불린 == []


# 개인화

_특징 = {"personal_color": "웜톤", "skin_type": "복합", "skin_concern": ["모공"]}


@pytest.mark.asyncio
async def test_프로필과_맞는_비율로_점수를_낸다():
    맥락 = _맥락(user_profile={
        "personal_color": "SPRING_WARM", "skin_type": "OILY_DEHYDRATED",
        "skin_concerns": ["ACNE"],
    })
    결과 = await personalization([_상품(feature_json=_특징)], 맥락)
    # 색, 피부 타입은 맞고 고민은 다르다
    assert 결과["p1"] == pytest.approx(66.67)


@pytest.mark.asyncio
async def test_BE의_수분부족지성은_복합으로_본다():
    맥락 = _맥락(user_profile={"skin_type": "OILY_DEHYDRATED"})
    결과 = await personalization([_상품(feature_json={"skin_type": "복합"})], 맥락)
    assert 결과["p1"] == 100


@pytest.mark.asyncio
async def test_전체_인기_기준이면_개인화는_None이다():
    맥락 = _맥락(spec={"target": Target.POPULAR}, user_profile={"skin_type": "DRY"})
    결과 = await personalization([_상품(feature_json={"skin_type": "건성"})], 맥락)
    assert 결과 == {"p1": None}


@pytest.mark.asyncio
async def test_특징이_없거나_비교할_항목이_없으면_개인화는_None이다():
    맥락 = _맥락(user_profile={"skin_type": "DRY"})
    결과 = await personalization(
        [_상품("p1", feature_json=None), _상품("p2", feature_json={"personal_color": "웜톤"})],
        맥락,
    )
    assert 결과 == {"p1": None, "p2": None}


# 조건 일치

@pytest.mark.asyncio
async def test_질의_특징과_맞는_비율로_점수를_낸다():
    맥락 = _맥락(spec={"features": {"texture": "가벼운", "finish": "매트"}})
    상품들 = [
        _상품("p1", feature_json={"texture": "가벼운", "finish": "매트"}),
        _상품("p2", feature_json={"texture": "중간", "finish": "글로우"}),
    ]
    결과 = await query_fit(상품들, 맥락)
    # 제형이 한 칸 멀면 0.6 만 맞는다
    assert 결과 == {"p1": 100, "p2": pytest.approx(30)}


@pytest.mark.asyncio
async def test_비교할_특징이_없는_상품은_None이고_맞지_않는_상품은_0이다():
    """특징이 없는 상품을 0 으로 두면 맞지 않는 상품과 구분되지 않는다."""
    맥락 = _맥락(spec={"features": {"finish": "매트"}})
    상품들 = [
        _상품("빈", feature_json={}),
        _상품("없음", feature_json=None),
        _상품("다른_항목만", feature_json={"texture": "가벼운"}),
        _상품("불일치", feature_json={"finish": "글로우"}),
    ]
    결과 = await query_fit(상품들, 맥락)
    assert 결과 == {"빈": None, "없음": None, "다른_항목만": None, "불일치": 0}


@pytest.mark.asyncio
async def test_질의에_특징이_없으면_조건_일치는_None이다():
    결과 = await query_fit([_상품(feature_json={"texture": "가벼운"})], _맥락())
    assert 결과 == {"p1": None}


# 인기

@pytest.mark.asyncio
async def test_후기가_적은_높은_평점은_평균_쪽으로_당긴다():
    맥락 = _맥락(spec={"target": Target.POPULAR})
    상품들 = [
        _상품("적음", average_score=5.0, review_count=2),
        _상품("많음", average_score=4.6, review_count=2000),
        _상품("보통", average_score=4.0, review_count=20),
    ]
    결과 = await popularity(상품들, 맥락)
    assert 결과["많음"] > 결과["적음"]
    # 평균 4.533, (2·5 + 20·4.533)/22 = 4.576 → (4.576−1)/4
    assert 결과["적음"] == pytest.approx(89.39, abs=0.01)


@pytest.mark.asyncio
async def test_전체_인기_기준이_아니거나_평점이_없으면_인기는_None이다():
    상품들 = [_상품("p1", average_score=4.5, review_count=10), _상품("p2", average_score=None)]
    assert await popularity(상품들, _맥락()) == {"p1": None, "p2": None}
    결과 = await popularity(상품들, _맥락(spec={"target": Target.POPULAR}))
    assert 결과["p1"] is not None
    assert 결과["p2"] is None
