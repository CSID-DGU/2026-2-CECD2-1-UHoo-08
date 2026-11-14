"""간단 채점 노드가 지켜야 할 성질.

BE 는 대체 후보의 유사도를 점수 분해의 similarity 항목으로 읽는다. 이 항목이 빠지거나
총점에 섞이면 화면 숫자가 틀린다.
"""
import pytest

from graph.nodes import score_lite as 노드
from services import product_meta, scoring


@pytest.fixture
def 대역(monkeypatch):
    """상품 정보와 채점을 가짜로 둔다. 총점은 정해 둔 값을 돌려준다."""
    def 세우기(총점: dict[str, int], 메타_없는=()):
        기록: dict = {"채점": []}

        async def ensure(있던, ids):
            return {**있던, **{pid: {"name": pid} for pid in ids if pid not in 메타_없는}}

        async def score_products(상품들, ctx, prior, *, lite):
            기록["채점"].append({"ids": [p["product_id"] for p in 상품들], "lite": lite,
                                "유사도": [p["similarity"] for p in 상품들]})
            매긴 = [{"product_id": p["product_id"], "total": 총점[p["product_id"]],
                     "breakdown": [{"key": "review", "label": "후기 일치", "score": 70, "weight": 1.0}]}
                    for p in 상품들]
            return sorted(매긴, key=lambda s: s["total"], reverse=True)

        monkeypatch.setattr(product_meta, "ensure", ensure)
        monkeypatch.setattr(scoring, "score_products", score_products)
        return 기록

    return 세우기


def _상태(**값):
    return {"job_id": "j1", "user_id": "u1", "scenario": "S1_EVALUATE",
            "query_spec": {"request_type": "EVALUATE", "target": "SELF"}, **값}


def _대체(*쌍):
    return [{"product_id": pid, "similarity": s} for pid, s in 쌍]


@pytest.mark.asyncio
async def test_대체_후보_점수_분해_맨_앞에_비슷한_정도를_둔다(대역):
    기록 = 대역({"a1": 80})
    나옴 = await 노드.score_lite(_상태(alternatives=_대체(("a1", 0.734))))

    assert 기록["채점"][0]["lite"] is True
    assert 기록["채점"][0]["유사도"] == [0.734]
    카드 = 나옴["alternatives"][0]
    assert 카드["breakdown"][0] == {
        "key": "similarity", "label": "비슷한 정도", "score": 73.4, "weight": 0.0}
    assert 카드["breakdown"][1]["key"] == "review"
    # 비슷한 정도는 총점에 섞지 않는다
    assert 카드["total"] == 80 and 카드["similarity"] == 0.734


@pytest.mark.asyncio
async def test_하한_미만은_빼고_그_수를_남긴다(대역):
    대역({"a1": 80, "a2": 49, "a3": 50, "a4": 10})
    나옴 = await 노드.score_lite(_상태(alternatives=_대체(
        ("a1", 0.9), ("a2", 0.8), ("a3", 0.7), ("a4", 0.6))))
    assert [a["product_id"] for a in 나옴["alternatives"]] == ["a1", "a3"]
    assert 나옴["alternatives_dropped_count"] == 2


@pytest.mark.asyncio
async def test_상위_5개만_남긴다(대역):
    대역({f"a{i}": 90 - i for i in range(8)})
    나옴 = await 노드.score_lite(_상태(alternatives=_대체(*[(f"a{i}", 0.5) for i in range(8)])))
    assert [a["product_id"] for a in 나옴["alternatives"]] == ["a0", "a1", "a2", "a3", "a4"]
    # 상위 몇 개로 자른 것은 하한에 걸려 뺀 수가 아니다
    assert 나옴["alternatives_dropped_count"] == 0


@pytest.mark.asyncio
async def test_유사도는_0에서_100_사이로_자른다(대역):
    대역({"a1": 60, "a2": 60})
    나옴 = await 노드.score_lite(_상태(alternatives=_대체(("a1", 1.2), ("a2", None))))
    점수 = {a["product_id"]: a["breakdown"][0]["score"] for a in 나옴["alternatives"]}
    assert 점수 == {"a1": 100.0, "a2": 0.0}


@pytest.mark.asyncio
async def test_대체_후보가_없으면_채점하지_않는다(대역):
    기록 = 대역({})
    나옴 = await 노드.score_lite(_상태(alternatives=[]))
    assert 나옴 == {"alternatives": [], "alternatives_dropped_count": 0}
    assert 기록["채점"] == []


@pytest.mark.asyncio
async def test_상품_평가가_아니면_후보를_채점해_scored에_쓴다(대역):
    기록 = 대역({"p1": 70, "p2": 40})
    나옴 = await 노드.score_lite(_상태(scenario="HOME_ENV", candidates=_대체(("p1", 0.5), ("p2", 0.4))))
    assert [s["product_id"] for s in 나옴["scored"]] == ["p1", "p2"]
    assert 기록["채점"][0]["lite"] is True
    assert "alternatives" not in 나옴
    assert await 노드.score_lite(_상태(scenario="HOME_ENV", candidates=[])) == {"scored": []}
