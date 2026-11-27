"""예산 나누기 · 조합 고르기 · 두 노드. DB 와 LLM 없이 돈다."""
import pytest

from contracts.result import BundleOption, BundleSlot
from graph.nodes import budget as 예산_노드
from graph.nodes import bundle as 세트_노드
from rules.budget_split import split
from rules.bundle_pick import MAX_BUNDLES, pick

단계 = [
    {"category": "skincare", "product_type": "토너", "label": "토너"},
    {"category": "skincare", "product_type": "세럼", "label": "세럼"},
    {"category": "skincare", "product_type": "크림", "label": "크림"},
]


# ── 예산 나누기 ──────────────────────────────────────────────────

def test_종류별_비중으로_나누고_합은_예산과_같다():
    칸들 = split(100000, 단계)
    assert [c["slot_key"] for c in 칸들] == ["toner", "serum", "cream"]
    assert [c["amount"] for c in 칸들] == [25600, 38500, 35900]
    assert sum(c["amount"] for c in 칸들) == 100000
    assert 칸들[1] == {"slot_key": "serum", "label": "세럼", "category": "skincare",
                     "product_type": "세럼", "amount": 38500}


def test_같은_종류가_두_번이면_칸_키에_번호를_붙이고_모르는_종류는_순번_키다():
    칸들 = split(30000, [{"product_type": "토너", "label": "토너"},
                         {"product_type": "토너", "label": "닦토"},
                         {"product_type": None, "label": "뭐든"}])
    assert [c["slot_key"] for c in 칸들] == ["toner", "toner_2", "slot3"]


def test_예산이나_단계가_없으면_빈_계획이다():
    assert split(None, 단계) == [] and split(100000, []) == []


# ── 조합 고르기 ──────────────────────────────────────────────────

def _옵션(*쌍):
    return [{"product_id": pid, "price": 가격, "score": 점수} for pid, 가격, 점수 in 쌍]


칸들 = [
    {"slot_key": "toner", "label": "토너", "amount": 25000,
     "options": _옵션(("t1", 30000, 90), ("t2", 15000, 82), ("t3", 9000, 70))},
    {"slot_key": "serum", "label": "세럼", "amount": 40000,
     "options": _옵션(("s1", 45000, 95), ("s2", 28000, 85), ("s3", 18000, 72))},
    {"slot_key": "cream", "label": "크림", "amount": 35000,
     "options": _옵션(("c1", 38000, 88), ("c2", 22000, 84), ("c3", 12000, 75))},
]


def _ids(b):
    return [o["product_id"] for _, o in b["picks"]]


def test_예산_안에서_성격별로_고르고_같은_조합은_한_번만():
    고른 = pick(칸들, 100000)
    assert 1 <= len(고른) <= MAX_BUNDLES
    assert all(b["total_price"] <= 100000 and b["over_budget_reason"] is None for b in 고른)
    assert len({tuple(_ids(b)) for b in 고른}) == len(고른)

    by = {b["label"]: b for b in 고른}
    # 균형형: 예산 안 평균 점수 최고. 최고점끼리(t1+s1+c1 = 113,000원)는 넘으므로
    # 크림만 한 단계 내린 t1+s1+c2 (97,000원, 평균 89.7)
    assert _ids(by["균형형"]) == ["t1", "s1", "c2"] and by["균형형"]["total_price"] == 97000
    # 알뜰형: 균형형 평균(89.7)에서 10점 안쪽 중 가장 쌈
    assert _ids(by["알뜰형"]) == ["t2", "s2", "c3"] and by["알뜰형"]["total_price"] == 55000
    # 세럼 집중형은 균형형과 같은 조합(s1 포함)이라 싣지 않고, 다른 조합으로 채운다
    assert [b["label"] for b in 고른] == ["균형형", "알뜰형", "가성비형", "다른 조합", "다른 조합"]


def test_핵심_칸_집중형은_예산이_큰_칸의_최고점_후보를_지킨다():
    by = {b["label"]: b for b in pick(칸들, 80000)}
    # 균형형은 세럼을 s2 로 낮추지만, 집중형은 세럼 s1 을 지키고 나머지를 낮춘다
    assert _ids(by["균형형"]) == ["t1", "s2", "c2"]
    assert _ids(by["세럼 집중형"]) == ["t2", "s1", "c3"]


def test_예산_안에_조합이_없으면_가장_싼_조합과_초과_이유():
    [b] = pick(칸들, 30000)
    assert _ids(b) == ["t3", "s3", "c3"] and b["total_price"] == 39000
    assert "9,000원 초과" in b["over_budget_reason"]


def test_후보가_없는_칸은_빼고_조합한다():
    고른 = pick([*칸들[:2], {"slot_key": "cream", "label": "크림", "options": []}], 100000)
    assert all(len(b["picks"]) == 2 for b in 고른)
    assert pick([{"slot_key": "x", "label": "x", "options": []}], 100000) == []


# ── 노드 ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_budget_노드는_질의의_총예산과_단계로_칸을_나눈다():
    상태 = {"query_spec": {"budget": {"total": 100000}, "bundle_steps": 단계}}
    계획 = (await 예산_노드.budget(상태))["budget_plan"]
    assert [c["slot_key"] for c in 계획] == ["toner", "serum", "cream"]


@pytest.mark.asyncio
async def test_bundle_노드는_계약대로_세트와_교체_후보를_낸다():
    계획 = split(100000, 단계)
    후보, 점수, 메타 = [], [], {}
    for 칸 in 칸들:
        for o in 칸["options"]:
            후보.append({"product_id": o["product_id"], "slot_key": 칸["slot_key"]})
            점수.append({"product_id": o["product_id"], "total": o["score"], "breakdown": []})
            메타[o["product_id"]] = {"name": f"상품 {o['product_id']}", "brand": "B", "price": o["price"]}
    # 가격을 모르는 후보는 쓰지 않는다
    후보.append({"product_id": "t9", "slot_key": "toner"})
    점수.append({"product_id": "t9", "total": 99, "breakdown": []})
    메타["t9"] = {"name": "가격 모름", "brand": "B", "price": None}

    상태 = {"budget_plan": 계획, "candidates": 후보, "scored": 점수, "product_meta": 메타,
          "query_spec": {"budget": {"total": 100000}}}
    나옴 = await 세트_노드.bundle(상태)

    for b in 나옴["bundles"]:
        세트 = BundleOption.model_validate(b)
        assert [i.slot_key for i in 세트.items] == ["toner", "serum", "cream"]
        assert 세트.total_price == sum(i.price for i in 세트.items)
        assert "t9" not in [i.product_id for i in 세트.items]
    # 교체 후보는 BE 가 읽는 camelCase 모양이다
    [토너, *_] = 나옴["bundle_slots"]
    BundleSlot.model_validate(토너)
    assert 토너["slotKey"] == "toner" and 토너["candidates"][0] == {
        "productId": "t1", "name": "상품 t1", "price": 30000, "score": 90}


def test_세트_후보는_칸마다_고르게_채점한다():
    """검색 문장이 칸마다 달라 유사도를 견줄 수 없다. 전체 상위로 자르면 한 칸이 통째로 빠진다."""
    from graph.nodes.score import 채점_상한, 채점_대상

    후보 = ([{"product_id": f"s{i}", "slot_key": "serum", "similarity": 0.9} for i in range(20)]
          + [{"product_id": f"c{i}", "slot_key": "cream", "similarity": 0.8} for i in range(20)]
          + [{"product_id": f"t{i}", "slot_key": "toner", "similarity": 0.5} for i in range(20)])
    고른 = 채점_대상(후보)
    칸별 = {k: sum(1 for c in 고른 if c["slot_key"] == k) for k in ("serum", "cream", "toner")}
    assert 칸별 == {"serum": 채점_상한 // 3, "cream": 채점_상한 // 3, "toner": 채점_상한 // 3}


def test_칸이_없는_후보는_전처럼_유사도_상위로_자른다():
    from graph.nodes.score import 채점_상한, 채점_대상

    후보 = [{"product_id": f"p{i}", "similarity": i / 100} for i in range(50)]
    고른 = 채점_대상(후보)
    assert len(고른) == 채점_상한 and 고른[0]["product_id"] == "p49"
