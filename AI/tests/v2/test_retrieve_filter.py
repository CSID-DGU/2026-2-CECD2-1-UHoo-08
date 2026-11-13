"""검색 필터가 지켜야 할 성질.

예산은 어기면 안 된다. 반대로 모른다는 이유로 빼면 정보가 빈 상품은 영영 추천되지 않는다.
"""
import pytest

from contracts.query_spec import Budget, QuerySpec, RequestType
from rules.retrieve_filter import apply


def _스펙(**값) -> QuerySpec:
    return QuerySpec(request_type=RequestType.SEARCH, **값)


def _후보(pid, 유사도=0.5, **값):
    return {"product_id": pid, "source": "retrieve", "similarity": 유사도, **값}


def _ids(결과):
    return [c["product_id"] for c in 결과]


def test_제품_종류가_다르면_빼고_모르면_남긴다():
    메타 = {
        "p1": {"feature_json": {"product_type": "쿠션"}},
        "p2": {"feature_json": {"product_type": "파운데이션"}},
        "p3": {"feature_json": {}},
    }
    결과 = apply([_후보("p1"), _후보("p2"), _후보("p3")], 메타,
                 _스펙(features={"product_type": "쿠션"}), ingredients={}, limit=10)
    assert _ids(결과) == ["p1", "p3"]


@pytest.mark.parametrize("가격, 남음", [(29999, True), (30000, True), (30001, False), (None, False)])
def test_예산_상한을_넘거나_가격을_모르면_뺀다(가격, 남음):
    결과 = apply([_후보("p1")], {"p1": {"price": 가격}},
                 _스펙(budget=Budget(max=30000)), ingredients={}, limit=10)
    assert bool(결과) is 남음


def test_예산이_없으면_가격을_몰라도_남긴다():
    결과 = apply([_후보("p1")], {"p1": {"price": None}}, _스펙(), ingredients={}, limit=10)
    assert _ids(결과) == ["p1"]


def test_제외_성분이_들어_있으면_뺀다():
    성분 = {"p1": ["레티놀", "나이아신아마이드"], "p2": ["히알루론산"], "p3": []}
    결과 = apply([_후보("p1"), _후보("p2"), _후보("p3")], {},
                 _스펙(exclude_ingredients=["레티놀"]), ingredients=성분, limit=10)
    # 성분을 모르는 p3 는 남긴다
    assert _ids(결과) == ["p2", "p3"]


def test_성분은_띄어쓰기와_대소문자를_무시하고_견준다():
    결과 = apply([_후보("p1")], {}, _스펙(exclude_ingredients=["Salicylic Acid"]),
                 ingredients={"p1": ["salicylicacid"]}, limit=10)
    assert 결과 == []


def test_성분을_읽지_못했으면_제외_성분은_건너뛴다():
    결과 = apply([_후보("p1")], {}, _스펙(exclude_ingredients=["레티놀"]),
                 ingredients=None, limit=10)
    assert _ids(결과) == ["p1"]


def test_나머지_특징은_거르지_않는다():
    메타 = {"p1": {"feature_json": {"finish": "글로우"}}}
    결과 = apply([_후보("p1")], 메타, _스펙(features={"finish": "매트"}), ingredients={}, limit=10)
    assert _ids(결과) == ["p1"]


def test_유사도_순_상위만_남긴다():
    후보 = [_후보(f"p{i}", i / 10) for i in range(5)]
    assert _ids(apply(후보, {}, _스펙(), ingredients={}, limit=3)) == ["p4", "p3", "p2"]


def test_칸이_있으면_칸마다_상위를_남긴다():
    후보 = [
        _후보("t1", 0.9, slot_key="토너"), _후보("t2", 0.8, slot_key="토너"),
        _후보("t3", 0.7, slot_key="토너"), _후보("c1", 0.6, slot_key="크림"),
    ]
    결과 = apply(후보, {}, _스펙(), ingredients={}, limit=2)
    assert _ids(결과) == ["t1", "t2", "c1"]
