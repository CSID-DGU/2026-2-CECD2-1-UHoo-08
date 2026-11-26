"""추천 결과 스키마가 지켜야 할 성질.

이 모양이 AI·BE·FE 세 곳에서 같아야 한다. 한 곳만 고쳐지면 화면이 빈칸을
그리거나 저장된 결과를 다시 읽지 못한다.
"""
import json
import pathlib

import pytest
from pydantic import ValidationError

from contracts.score import ScoreItem
from contracts.result import (
    Badge,
    BundleItem,
    BundleOption,
    BundleSlot,
    Clarify,
    ExcludedItem,
    RecommendationResult,
    ResultItem,
)


def _항목(**덮어쓰기) -> ResultItem:
    기본 = dict(product_id="p1", name="세럼", brand="브랜드", total_score=80)
    기본.update(덮어쓰기)
    return ResultItem(**기본)


def test_화면으로_나갈_때_camelCase가_된다():
    결과 = RecommendationResult(job_id="j1", scenario="S2_SEARCH", items=[_항목(price=23000)])
    나감 = 결과.model_dump(mode="json", by_alias=True)
    assert "jobId" in 나감
    assert "productId" in 나감["items"][0]
    assert "totalScore" in 나감["items"][0]
    assert "product_id" not in 나감["items"][0]


def test_파이썬_쪽에서는_snake_case로_만든다():
    """두 이름을 다 받아주지 않으면 노드 코드가 화면 관례를 따라가야 한다."""
    항목 = ResultItem(product_id="p1", name="n", brand="b", total_score=50, image_url=None)
    assert 항목.product_id == "p1"


def test_점수_항목이_늘어도_스키마를_고치지_않는다():
    """breakdown 이 고정 키였다면 항목마다 스키마 수정이 필요하다."""
    항목 = _항목(breakdown=[
        ScoreItem(key="budget_fit", label="예산 적합", score=90, weight=0.3),
        ScoreItem(key="env_fit", label="환경 적합", score=70, weight=0.2),
        ScoreItem(key="value_signal", label="가성비", score=60, weight=0.5),
    ])
    assert len(항목.breakdown) == 3


def test_총점은_0에서_100_사이다():
    with pytest.raises(ValidationError):
        _항목(total_score=101)


def test_모르는_필드를_거부한다():
    with pytest.raises(ValidationError):
        _항목(discount=1000)


def test_제외_항목은_사유를_반드시_갖는다():
    """사유 없이 빼면 화면에 이유를 못 쓴다."""
    with pytest.raises(ValidationError):
        ExcludedItem(product_id="p1")
    빠짐 = ExcludedItem(product_id="p1", reason="OWNED", detail="이미 쓰고 있어요")
    assert 빠짐.reason.value == "OWNED"


def test_배지_문구는_비어_있을_수_없다():
    with pytest.raises(ValidationError):
        Badge(type="ENV", text="")


def test_세트_조합은_제품이_하나_이상이다():
    with pytest.raises(ValidationError):
        BundleOption(label="균형형", total_price=50000, items=[])
    조합 = BundleOption(label="균형형", total_price=50000, items=[_세트_제품()])
    assert 조합.over_budget_reason is None


def _세트_제품(**덮어쓰기) -> dict:
    return {"productId": "p1", "name": "토너", "brand": "브랜드", "totalScore": 80, **덮어쓰기}


def test_세트_제품의_칸_정보를_왕복한다():
    조합 = BundleOption.model_validate({
        "label": "균형형", "totalPrice": 22000,
        "items": [_세트_제품(slotKey="toner", slotLabel="토너")],
    })
    나감 = 조합.model_dump(mode="json", by_alias=True)["items"][0]
    assert (나감["slotKey"], 나감["slotLabel"]) == ("toner", "토너")


def test_칸_정보_없이_저장된_조합도_읽는다():
    조합 = BundleOption.model_validate({"label": "균형형", "totalPrice": 22000, "items": [_세트_제품()]})
    assert 조합.items[0].slot_key is None and 조합.items[0].slot_label is None


@pytest.mark.parametrize("값", [{"slotKey": ""}, {"slotLabel": ""}])
def test_칸_정보는_빈_문자열일_수_없다(값):
    with pytest.raises(ValidationError):
        BundleItem.model_validate(_세트_제품(**값))


def test_일반_카드에는_칸_정보를_넣을_수_없다():
    with pytest.raises(ValidationError):
        ResultItem.model_validate(_세트_제품(slotKey="toner"))


_칸 = {"slotKey": "toner", "label": "토너", "candidates": [
    {"productId": "p1", "name": "토너", "price": 20500, "score": 88},
]}


def test_칸별_후보를_왕복한다():
    assert BundleSlot.model_validate(_칸).model_dump(mode="json", by_alias=True) == _칸


@pytest.mark.parametrize("후보", [
    {"productId": "p1", "name": "토너", "score": 88},
    {"productId": "p1", "name": "토너", "price": None, "score": 88},
    {"productId": "p1", "name": "토너", "price": -1, "score": 88},
    {"productId": "p1", "name": "토너", "price": 20500, "score": 101},
    {"productId": "", "name": "토너", "price": 20500, "score": 88},
])
def test_합계를_계산할_수_없는_후보를_거부한다(후보):
    with pytest.raises(ValidationError):
        BundleSlot.model_validate({**_칸, "candidates": [후보]})


@pytest.mark.parametrize("값", [{"slotKey": ""}, {"label": ""}])
def test_칸은_키와_이름이_있어야_한다(값):
    with pytest.raises(ValidationError):
        BundleSlot.model_validate({**_칸, **값})


def test_되물을_것이_없으면_clarify는_None이다():
    결과 = RecommendationResult(job_id="j1", scenario="S2_SEARCH")
    assert 결과.clarify is None
    assert 결과.items == []


def test_되묻는_결과는_질문을_담는다():
    결과 = RecommendationResult(
        job_id="j1",
        scenario="S6_BUNDLE",
        clarify=Clarify(question="예산을 알려주세요", options=["5만원", "10만원"]),
    )
    나감 = 결과.model_dump(by_alias=True)["clarify"]
    assert 나감["question"]
    assert 나감["missingFields"] == []


홈_블록 = ("conditions", "counts", "pairs", "replacement", "schedule", "uncomparedCount", "checkedUserProductIds")
BE_샘플 = pathlib.Path(__file__).resolve().parents[3] / "BE" / "src" / "test" / "resources" / "ai-results"
_제품쌍 = {
    "a": {"userProductId": "up1", "name": "토너"},
    "b": {"userProductId": "up2", "name": "크림"},
    "level": "SEPARATE",
}


def test_홈_블록은_채우지_않으면_null이다():
    """null 은 분석 전이다. 빈 목록이 기본값이면 분석 전 카드가 문제없는 카드로 보인다."""
    나감 = RecommendationResult(job_id="j1", scenario="S2_SEARCH").model_dump(mode="json", by_alias=True)
    assert all(나감[키] is None for 키 in 홈_블록)


def test_빈_목록은_null과_구분해서_남는다():
    결과 = RecommendationResult(job_id="j1", scenario="HOME_ENV", conditions=[], pairs=[])
    나감 = 결과.model_dump(mode="json", by_alias=True)
    assert 나감["conditions"] == [] and 나감["pairs"] == []


def test_환경_블록을_왕복한다():
    조건 = {"key": "UV_PROTECT", "label": "자외선 차단", "basis": "6 이상 22일",
            "covered": True, "coveredBy": "선크림"}
    결과 = RecommendationResult.model_validate(
        {"jobId": "j1", "scenario": "HOME_ENV", "conditions": [조건]}
    )
    assert 결과.model_dump(mode="json", by_alias=True)["conditions"] == [조건]


def test_루틴_블록을_왕복한다():
    블록 = {
        "counts": {"ok": 1, "separate": 2, "avoid": 0},
        "pairs": [{**_제품쌍, "title": "나눠 쓰세요", "reason": "자극이 커져요"}],
        "replacement": {
            "replaceTarget": _제품쌍["a"],
            "message": "바꾸는 걸 권해요",
            "items": [{"productId": "p1", "name": "세럼", "brand": "브랜드",
                       "price": 19800, "totalScore": 84, "badge": "괜찮아요"}],
        },
        "schedule": {"morning": ["토너"], "evening": ["크림"], "tip": "저녁에 쓰세요"},
        "uncomparedCount": 1,
        "checkedUserProductIds": ["up1", "up2", "up3"],
    }
    결과 = RecommendationResult.model_validate({"jobId": "j1", "scenario": "HOME_ROUTINE", **블록})
    나감 = 결과.model_dump(mode="json", by_alias=True)
    assert {키: 나감[키] for 키 in 블록} == 블록


@pytest.mark.parametrize("덮어쓰기", [
    {"pairs": [{**_제품쌍, "level": "GOOD"}]},
    {"pairs": [{**_제품쌍, "a": {"name": "토너"}}]},
    {"counts": {"ok": 1, "separate": 2}},
    {"counts": {"ok": -1, "separate": 0, "avoid": 0}},
    {"uncomparedCount": -1},
    {"checkedUserProductIds": "up1"},
    {"conditions": [{"label": "자외선 차단"}]},
    {"replacement": {"message": "바꾸세요"}},
])
def test_잘못된_홈_블록을_거부한다(덮어쓰기):
    with pytest.raises(ValidationError):
        RecommendationResult.model_validate({"jobId": "j1", "scenario": "HOME_ROUTINE", **덮어쓰기})


@pytest.mark.parametrize("파일", ["HOME_ROUTINE.json", "HOME_ENV.json", "S6_BUNDLE.json"])
def test_BE가_읽는_샘플이_계약을_통과한다(파일):
    """BE 는 이 샘플로 API 를 테스트한다. 어긋나면 AI 가 채운 값을 BE 가 못 읽는다."""
    RecommendationResult.model_validate(json.loads((BE_샘플 / 파일).read_text(encoding="utf-8")))
