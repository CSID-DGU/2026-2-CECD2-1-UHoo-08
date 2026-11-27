"""루틴 점검 노드와 아침 · 저녁 순서. DB 없이 돈다."""
import pytest

from graph.nodes import compatibility as 노드
from rules.routine_schedule import TIP_AVOID, TIP_SEPARATE, build_schedule

_규칙 = [
    {"ingredient_a": "글라이콜릭애씨드", "ingredient_b": "레티놀", "level": "AVOID", "advice": "같이 쓰면 자극"},
    {"ingredient_a": "레티놀", "ingredient_b": "비타민C", "level": "SEPARATE", "advice": "아침 비타민C, 저녁 레티놀"},
]


def _항목(upid, 이름, 종류, 성분, 카테고리="skincare"):
    return {"user_product_id": upid, "product_id": f"p-{upid}", "name": 이름, "category": 카테고리,
            "feature_json": {"product_type": 종류}, "ingredients": 성분}


보유 = [
    _항목("u1", "레티놀 크림", "크림", ["레티놀", "세라마이드"]),
    _항목("u2", "비타C 세럼", "세럼", ["비타민C"]),
    _항목("u3", "AHA 토너", "토너", ["글라이콜릭애씨드"]),
    _항목("u4", "수분 에센스", "에센스", ["히알루론산"]),
    _항목("u5", "성분 모름 로션", "로션", []),
    _항목("u6", "선크림", "선크림", ["티타늄디옥사이드"], 카테고리="sun"),
    _항목("u7", "쿠션", "쿠션", ["나이아신아마이드"], 카테고리="base"),
]


def test_보유_제품_쌍마다_판정하고_센_쌍부터_적는다():
    점검 = 노드.check_routine(보유, _규칙)
    assert [(p["a"]["user_product_id"], p["b"]["user_product_id"], p["level"]) for p in 점검["pairs"]] == [
        ("u1", "u3", "AVOID"), ("u1", "u2", "SEPARATE"),
    ]
    # 성분은 각 제품 쪽 순서로 적는다
    assert 점검["pairs"][0]["title"] == "레티놀 + 글라이콜릭애씨드"
    assert 점검["pairs"][0]["reason"] == "같이 쓰면 자극"
    # 견준 제품 6개(성분 모름 1개 제외) → 15쌍 중 2쌍이 걸림
    assert 점검["counts"] == {"ok": 13, "separate": 1, "avoid": 1}
    assert 점검["uncompared_count"] == 1
    assert "u5" not in 점검["checked_user_product_ids"]


def test_시간대를_나눌_쌍은_레티놀을_저녁_비타민C를_아침에_둔다():
    일정 = 노드.check_routine(보유, _규칙)["schedule"]
    assert "레티놀 크림" in 일정["evening"] and "레티놀 크림" not in 일정["morning"]
    assert "비타C 세럼" in 일정["morning"] and "비타C 세럼" not in 일정["evening"]
    # 나누지 않아도 되는 스킨케어는 둘 다, 선크림은 아침 마지막, 메이크업은 넣지 않는다
    assert 일정["morning"][-1] == "선크림" and "선크림" not in 일정["evening"]
    assert "쿠션" not in 일정["morning"] + 일정["evening"]
    # 바르는 단계 순서
    assert 일정["evening"].index("AHA 토너") < 일정["evening"].index("수분 에센스") < 일정["evening"].index("레티놀 크림")
    assert 일정["tip"] == TIP_AVOID


def test_시간대_분리만_있으면_나눠_쓰라는_팁이고_없으면_팁이_없다():
    a = _항목("a", "레티놀", "크림", ["레티놀"])
    b = _항목("b", "비타C", "세럼", ["비타민C"])
    쌍 = [{"a_id": "a", "b_id": "b", "level": "SEPARATE", "ingredient_a": "레티놀", "ingredient_b": "비타민C"}]
    assert build_schedule([a, b], 쌍)["tip"] == TIP_SEPARATE
    assert build_schedule([a, b], [])["tip"] is None


@pytest.mark.asyncio
async def test_보유_제품이_하나뿐이면_규칙을_읽지_않는다(monkeypatch):
    async def 터짐():
        raise AssertionError("견줄 쌍이 없는데 규칙을 읽었다")
    monkeypatch.setattr(노드, "_rules", 터짐)
    점검 = (await 노드.compatibility({"inventory": 보유[:1]}))["routine_check"]
    assert 점검["pairs"] == [] and 점검["counts"] == {"ok": 0, "separate": 0, "avoid": 0}
