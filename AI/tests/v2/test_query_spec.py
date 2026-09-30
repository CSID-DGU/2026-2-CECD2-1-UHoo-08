"""QuerySpec 이 지켜야 할 성질.

Normalize 는 LLM이 채운다. 모델이 없는 값을 지어내거나 없는 필드를 붙여도
여기서 걸려야 재시도·되묻기로 넘어간다. 검증이 느슨하면 잘못 채워진 조건으로
걸러진 결과가 그대로 사용자에게 나간다.
"""
import pytest
from pydantic import ValidationError

from contracts.query_spec import (
    CONFIDENCE_THRESHOLD,
    REQUIRED_FIELDS,
    Budget,
    BundleStep,
    Category,
    QuerySpec,
    RequestType,
    Target,
    needs_clarification,
)


def test_요청_유형만_있으면_만들_수_있다():
    """검색은 조건이 하나도 없어도 성립한다. "추천해줘" 도 질의다."""
    spec = QuerySpec(request_type=RequestType.SEARCH)
    assert spec.target is Target.SELF
    assert spec.use_env is False
    assert spec.budget.max is None
    assert spec.missing_required() == ()


def test_정해진_카테고리만_받는다():
    """DB에 없는 카테고리가 들어오면 이후 필터가 조용히 0건을 만든다."""
    with pytest.raises(ValidationError):
        QuerySpec(request_type=RequestType.SEARCH, category="cushion")
    assert QuerySpec(request_type="SEARCH", category="base").category is Category.BASE


def test_모르는_필드를_거부한다():
    """LLM이 없는 필드를 붙이면 재시도해야 한다. 조용히 무시하면 안 된다."""
    with pytest.raises(ValidationError):
        QuerySpec(request_type=RequestType.SEARCH, skin_type="DRY")


def test_예산은_양수여야_한다():
    with pytest.raises(ValidationError):
        Budget(max=0)
    with pytest.raises(ValidationError):
        Budget(total=-1000)


def test_제품_상한과_세트_상한은_다른_필드다():
    """세트 요청의 10만원을 제품 하나의 상한으로 읽으면 안 된다."""
    spec = QuerySpec(
        request_type=RequestType.BUNDLE,
        budget=Budget(total=100_000),
        bundle_steps=[BundleStep(label="토너")],
    )
    assert spec.budget.max is None
    assert spec.missing_required() == ()


def test_조건은_공백과_중복을_털어낸다():
    spec = QuerySpec(
        request_type=RequestType.SEARCH,
        conditions=[" 여름 ", "여름", "", "  "],
        exclude_ingredients=["향료", "향료"],
    )
    assert spec.conditions == ["여름"]
    assert spec.exclude_ingredients == ["향료"]


@pytest.mark.parametrize(
    "spec, 기대",
    [
        (QuerySpec(request_type=RequestType.EVALUATE), ("base_product_ref",)),
        (QuerySpec(request_type=RequestType.EVALUATE, base_product_ref="라네즈 네오쿠션"), ()),
        (QuerySpec(request_type=RequestType.BUNDLE), ("budget.total", "bundle_steps")),
        (QuerySpec(request_type=RequestType.REFINE), ()),
    ],
)
def test_필수_필드가_비면_잡아낸다(spec, 기대):
    assert spec.missing_required() == 기대


def test_모든_요청_유형에_필수_필드표가_있다():
    """유형을 추가하고 표를 빠뜨리면 KeyError 로 터진다. 미리 막는다."""
    assert set(REQUIRED_FIELDS) == set(RequestType)


def test_확신이_낮으면_되묻는다():
    낮음 = QuerySpec(request_type=RequestType.SEARCH, confidence=CONFIDENCE_THRESHOLD - 0.01)
    높음 = QuerySpec(request_type=RequestType.SEARCH, confidence=CONFIDENCE_THRESHOLD)
    assert needs_clarification(낮음) is True
    assert needs_clarification(높음) is False


def test_필수_필드가_비면_확신이_높아도_되묻는다():
    spec = QuerySpec(request_type=RequestType.EVALUATE, confidence=1.0)
    assert needs_clarification(spec) is True


def test_confidence_는_0에서_1_사이다():
    with pytest.raises(ValidationError):
        QuerySpec(request_type=RequestType.SEARCH, confidence=1.5)


def test_빈_라벨의_세트_단계를_거부한다():
    """무엇을 찾아야 하는지 모르는 단계가 세트에 들어가면 안 된다.
    bundle_steps 가 비어 있지 않다는 이유로 필수 필드 검사도 통과해버린다."""
    from contracts.query_spec import BundleStep

    with pytest.raises(ValidationError):
        BundleStep(label="")
    with pytest.raises(ValidationError):
        BundleStep(label="   ")
    assert BundleStep(label=" 토너 ").label == "토너"
