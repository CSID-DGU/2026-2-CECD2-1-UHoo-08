"""결과 점검이 지켜야 할 성질.

화면에 의료 표현이나 효과 단정이 나가면 안 된다. 모양이 틀린 결과는 저장되기 전에 막는다.
"""
import pytest
from pydantic import ValidationError

from graph.nodes.guard import guard
from rules.guard_rules import fallback_reason, has_forbidden


@pytest.mark.parametrize("문장", [
    "피부 트러블을 치료해 줘요", "완치에 가까운 효과", "피부과 처방처럼", "진단 없이도",
    "의학적으로 검증된", "약효가 뛰어나요", "효과를 보장해요", "효과 보장", "100% 만족",
    "100 % 순한", "무조건 맞아요", "절대 자극이 없어요", "부작용이 없어요", "부작용 없음",
    "피부과 전문의 추천", "아토피에 좋아요", "여드름 개선", "지루성 피부염에 효과", "습진을 없애요",
])
def test_금지_표현을_찾는다(문장):
    assert has_forbidden(문장)


@pytest.mark.parametrize("문장", [
    "건성 피부에 맞고 매트한 마무리예요", "평소 쓰는 제품보다 약 30% 저렴해요",
    "요즘 언급이 늘고 있어요", "레티놀 세럼과 시간대를 나눠 쓰세요", "여드름 피부 사용자가 많이 써요",
    None, "",
])
def test_괜찮은_문장은_그대로_둔다(문장):
    assert not has_forbidden(문장)


def test_규칙_문장은_점수가_높은_두_항목으로_만든다():
    점수 = [{"key": "review", "label": "후기 일치", "score": 60, "weight": 0.3},
            {"key": "budget_fit", "label": "예산 적합", "score": 90, "weight": 0.3},
            {"key": "personalization", "label": "내 피부 적합", "score": 70, "weight": 0.4}]
    assert fallback_reason(점수) == "예산 적합, 내 피부 적합 점수가 높아요"
    assert fallback_reason([]) is None
    # 규칙 문장에는 금지 표현이 들어갈 수 없다
    assert not has_forbidden(fallback_reason(점수))


def _카드(pid, reason, badges=(), **값):
    return {
        "productId": pid, "name": "쿠션", "brand": "b", "imageUrl": None, "price": 20000,
        "totalScore": 80,
        "breakdown": [{"key": "review", "label": "후기 일치", "score": 80.0, "weight": 1.0}],
        "badges": list(badges), "reason": reason, "change": None, "rankDelta": None, **값,
    }


def _결과(**값):
    return {"jobId": "j1", "scenario": "S2_SEARCH",
            "query": {"raw": "", "category": None, "conditions": [], "budgetMax": None,
                      "budgetTotal": None, "target": "SELF", "useEnv": False, "valueSeeking": False},
            "items": [], "alternatives": [], "similarUserProducts": [], "bundles": [],
            "excluded": [], "clarify": None, **값}


@pytest.mark.asyncio
async def test_금지_표현이_든_이유는_규칙_문장으로_바꾸고_배지는_뺀다():
    원본 = _결과(
        items=[
            _카드("p1", "아토피에 좋아요", [
                {"type": "VALUE", "text": "효과 100% 보장"},
                {"type": "TREND", "text": "요즘 언급이 늘고 있어요"},
            ]),
            _카드("p2", "가볍게 잘 맞아요"),
        ],
        alternatives=[_카드("a1", "부작용 없는 순한 제품")],
    )
    나옴 = (await guard({"result": 원본}))["result"]

    assert 나옴["items"][0]["reason"] == "후기 일치 점수가 높아요"
    assert [b["type"] for b in 나옴["items"][0]["badges"]] == ["TREND"]
    assert 나옴["items"][1]["reason"] == "가볍게 잘 맞아요"
    assert 나옴["alternatives"][0]["reason"] == "후기 일치 점수가 높아요"
    # 받은 결과는 고치지 않는다
    assert 원본["items"][0]["reason"] == "아토피에 좋아요"


@pytest.mark.asyncio
async def test_홈_루틴의_안내_문장도_본다():
    원본 = _결과(
        scenario="HOME_ROUTINE",
        counts={"ok": 0, "separate": 0, "avoid": 1},
        pairs=[{"a": {"userProductId": "u1", "name": "A"}, "b": {"userProductId": "u2", "name": "B"},
                "level": "AVOID", "title": None, "reason": "같이 쓰면 피부염 치료가 늦어요"}],
        replacement={"replaceTarget": {"userProductId": "u1", "name": "A"},
                     "message": "무조건 바꾸세요", "items": []},
        schedule={"morning": ["A"], "evening": ["B"], "tip": "절대 섞지 마세요"},
        uncomparedCount=0, checkedUserProductIds=["u1", "u2"],
    )
    나옴 = (await guard({"result": 원본}))["result"]
    assert 나옴["pairs"][0]["reason"] is None
    assert 나옴["replacement"]["message"] is None
    assert 나옴["schedule"]["tip"] is None


@pytest.mark.asyncio
async def test_문제가_없으면_그대로_돌려준다():
    원본 = _결과(items=[_카드("p1", "가볍게 잘 맞아요")])
    assert (await guard({"result": 원본}))["result"] == 원본


@pytest.mark.asyncio
@pytest.mark.parametrize("망가뜨리기", [
    lambda r: r.pop("jobId"),
    lambda r: r.update(scenario="S9_NOPE"),
    lambda r: r["items"][0].update(totalScore=120),
    lambda r: r.update(모르는_칸=1),
])
async def test_계약을_어긴_결과는_막는다(망가뜨리기):
    결과 = _결과(items=[_카드("p1", "가볍게 잘 맞아요")])
    망가뜨리기(결과)
    with pytest.raises(ValidationError):
        await guard({"result": 결과})
