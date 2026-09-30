"""추천 결과 스키마가 지켜야 할 성질.

이 모양이 AI·BE·FE 세 곳에서 같아야 한다. 한 곳만 고쳐지면 화면이 빈칸을
그리거나 저장된 결과를 다시 읽지 못한다.
"""
import pytest
from pydantic import ValidationError

from contracts.score import ScoreItem
from contracts.result import (
    Badge,
    BundleOption,
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
    조합 = BundleOption(label="균형형", total_price=50000, items=[_항목()])
    assert 조합.over_budget_reason is None


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
    assert 결과.model_dump(by_alias=True)["clarify"]["question"]
