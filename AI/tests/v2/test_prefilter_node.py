"""PreFilter 노드가 지켜야 할 성질.

B 의 부품이 아직 없어도 경로가 끝까지 돌아야 한다. 반대로 부품이 있는데 그 안의
의존성이 빠졌다면 숨기지 말아야 한다.
"""
import sys
import types

import pytest

from graph.nodes import prefilter as 노드

_보유 = [
    {"user_product_id": "u1", "product_id": "o1", "name": "레티놀 세럼"},
    {"user_product_id": "u2", "product_id": "o2", "name": "비타민 토너"},
]


def _후보(*ids):
    return [{"product_id": pid, "source": "vector", "similarity": 0.5} for pid in ids]


def _상태(**값):
    return {
        "candidates": _후보("o1", "p1", "p2", "p3"),
        "inventory": _보유,
        "product_meta": {pid: {"name": f"상품{pid}"} for pid in ("o1", "p1", "p2", "p3")},
        "query_spec": {"request_type": "SEARCH", "target": "SELF"},
        **값,
    }


@pytest.fixture
def 성분_부품(monkeypatch):
    """B 의 성분 부품을 가짜로 넣는다.

    p2 는 레티놀 세럼(u1)과 AVOID, 비타민 토너(u2)와 SEPARATE 이다.
    p3 는 비타민 토너(u2)와 SEPARATE 이다. p1 은 성분을 모른다.
    """
    기록: dict = {"성분": [], "보유": []}
    성분표 = {"p2": ["AHA"], "p3": ["비타민C"], "o1": ["레티놀"]}
    충돌표 = {
        "p2": [("u1", "AVOID"), ("u2", "SEPARATE")],
        "p3": [("u2", "SEPARATE")],
    }

    async def load_product_ingredients(ids):
        기록["성분"].append(list(ids))
        return {pid: 성분표.get(pid, []) for pid in ids}

    async def load_rules():
        return [{"규칙": 1}]

    def check_compatibility(inventory, product, rules):
        기록["보유"].append([항목["user_product_id"] for 항목 in inventory])
        있는 = {항목["user_product_id"] for 항목 in inventory}
        return [
            {"user_product_id": u, "ingredient_a": "a", "ingredient_b": "b",
             "level": 수준, "advice": None, "schedule": None}
            for u, 수준 in 충돌표.get(product["product_id"], []) if u in 있는
        ]

    import rules
    import services
    성분 = types.SimpleNamespace(load_product_ingredients=load_product_ingredients,
                               load_rules=load_rules)
    궁합 = types.SimpleNamespace(check_compatibility=check_compatibility)
    monkeypatch.setitem(sys.modules, "services.ingredient_store", 성분)
    monkeypatch.setitem(sys.modules, "rules.compatibility", 궁합)
    monkeypatch.setattr(services, "ingredient_store", 성분, raising=False)
    monkeypatch.setattr(rules, "compatibility", 궁합, raising=False)
    return 기록


@pytest.fixture
def 부품_없음(monkeypatch):
    monkeypatch.setitem(sys.modules, "services.ingredient_store", None)
    monkeypatch.setitem(sys.modules, "rules.compatibility", None)


@pytest.mark.asyncio
async def test_보유_제품과_충돌을_거르고_배지를_단다(성분_부품):
    나옴 = await 노드.prefilter(_상태())

    assert [c["product_id"] for c in 나옴["candidates"]] == ["p1", "p3"]
    assert [(e["product_id"], e["reason"]) for e in 나옴["excluded"]] == [
        ("o1", "OWNED"), ("p2", "CONFLICT")]
    assert 나옴["excluded"][1]["name"] == "상품p2"
    assert list(나옴["conflict_marks"]) == ["p3"]
    assert 나옴["conflict_marks"]["p3"][0]["advice"] == "비타민 토너와 시간대를 나눠 쓰세요"


@pytest.mark.asyncio
async def test_성분을_상품_정보에_채운다(성분_부품):
    나옴 = await 노드.prefilter(_상태())
    assert 성분_부품["성분"] == [["o1", "p1", "p2", "p3"]]
    assert 나옴["product_meta"]["p2"] == {"name": "상품p2", "ingredients": ["AHA"]}
    assert 나옴["product_meta"]["p1"]["ingredients"] == []


@pytest.mark.asyncio
async def test_상품_정보가_없는_상품에는_성분만_넣지_않는다(성분_부품):
    나옴 = await 노드.prefilter(_상태(product_meta={"p1": {"name": "쿠션"}}))
    assert set(나옴["product_meta"]) == {"p1"}


@pytest.mark.asyncio
async def test_다른_사람_기준이면_거르지_않는다(성분_부품):
    나옴 = await 노드.prefilter(_상태(query_spec={"request_type": "SEARCH", "target": "OTHER"}))
    assert 나옴 == {}
    assert 성분_부품["성분"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("보유", ["없음", None])
async def test_보유_제품_정보가_없으면_거르지_않는다(성분_부품, 보유):
    상태 = _상태()
    if 보유 == "없음":
        del 상태["inventory"]
    else:
        상태["inventory"] = None
    assert await 노드.prefilter(상태) == {}


@pytest.mark.asyncio
async def test_후보가_없으면_아무것도_하지_않는다(성분_부품):
    assert await 노드.prefilter(_상태(candidates=[])) == {}
    assert 성분_부품["성분"] == []


@pytest.mark.asyncio
async def test_성분_부품이_없으면_보유_제품만_거른다(부품_없음):
    나옴 = await 노드.prefilter(_상태())
    assert [c["product_id"] for c in 나옴["candidates"]] == ["p1", "p2", "p3"]
    assert [e["reason"] for e in 나옴["excluded"]] == ["OWNED"]
    assert 나옴["conflict_marks"] == {}


@pytest.mark.asyncio
async def test_성분_부품_안의_import_실패는_올린다(monkeypatch):
    """부품은 있는데 그 부품이 쓰는 모듈이 없는 경우다. 숨기면 충돌 판정이 조용히 꺼진다."""
    def 불러오기(이름):
        raise ModuleNotFoundError("No module named 'kiwipiepy'", name="kiwipiepy")

    monkeypatch.setattr(노드.importlib, "import_module", 불러오기)
    with pytest.raises(ModuleNotFoundError):
        await 노드.prefilter(_상태())


@pytest.mark.asyncio
async def test_바꿀_보유_제품은_충돌_판정에서_뺀다(성분_부품):
    나옴 = await 노드.prefilter(_상태(
        replace_target={"user_product_id": "u2", "product_id": "o2", "name": "비타민 토너"},
    ))
    assert set(성분_부품["보유"][0]) == {"u1"}
    # p3 는 바꿀 제품하고만 걸려서 배지가 없다
    assert "p3" not in 나옴["conflict_marks"]
    # 바꿀 제품 자체는 여전히 보유 제품이다
    assert [e["reason"] for e in 나옴["excluded"]] == ["OWNED", "CONFLICT"]


@pytest.mark.asyncio
async def test_기준_상품은_빼지_않고_판정을_남긴다(성분_부품):
    나옴 = await 노드.prefilter(_상태(base_product_id="p2", scenario="S1_EVALUATE"))
    assert "p2" in [c["product_id"] for c in 나옴["candidates"]]
    assert 나옴["base_conflicts"]["p2"]["owned"] is False
    assert [c["level"] for c in 나옴["base_conflicts"]["p2"]["conflicts"]] == ["AVOID", "SEPARATE"]


@pytest.mark.asyncio
async def test_세트의_같은_상품은_한_번만_조회한다(성분_부품):
    후보 = [{"product_id": "p3", "slot_key": "토너"}, {"product_id": "p3", "slot_key": "크림"}]
    나옴 = await 노드.prefilter(_상태(candidates=후보))
    assert 성분_부품["성분"] == [["p3"]]
    assert len(나옴["candidates"]) == 2


@pytest.mark.asyncio
async def test_앞서_남긴_제외_기록을_덮어쓰지_않는다(성분_부품):
    앞서 = [{"product_id": "x", "name": None, "reason": "OWNED", "detail": None}]
    나옴 = await 노드.prefilter(_상태(excluded=앞서))
    assert 나옴["excluded"][0]["product_id"] == "x"
    assert len(나옴["excluded"]) == 3
