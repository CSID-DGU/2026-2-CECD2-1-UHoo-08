"""되물을지를 정하는 구조 규칙을 본다.

LLM 이 매긴 숫자 대신 이 규칙이 되묻기를 정한다. 규칙이 틀리면 막연한 질문에
엉뚱한 추천이 나가거나, 분명한 질문에 쓸데없이 되묻게 된다.
"""
import pytest

from contracts.query_spec import Budget, BundleStep, QuerySpec, RequestType
from rules.clarify import is_underspecified, missing_fields, names_a_product, needs_clarification


def _스펙(**채운) -> QuerySpec:
    return QuerySpec(**{"request_type": RequestType.SEARCH, **채운})


def test_단서가_하나도_없으면_막연한_질문이다():
    assert is_underspecified(_스펙())


@pytest.mark.parametrize("채운", [
    {"category": "base"},
    {"features": {"finish": "매트"}},
    {"conditions": ["여름"]},
    {"budget": Budget(max=30000)},
    {"budget": Budget(total=100000)},
    {"base_product_ref": "어떤 쿠션"},
])
def test_단서가_하나라도_있으면_막연한_질문이_아니다(채운):
    assert not is_underspecified(_스펙(**채운))


@pytest.mark.parametrize("말, 알려_주나", [
    ("라운드랩 독도 토너", True),
    ("독도 토너", True),
    ("이거", False),
    ("그 선크림", False),
    ("이 제품", False),
    ("방금 그거", False),
    ("그 선크림?", False),                # 문장부호가 붙었다
    ("그 쿠션은", False),                 # 조사가 붙었다
    ("이거요", False),
    ("그 스킨", False),                   # 종류의 다른 이름이다
    ("달바 워터풀 선크림?", True),
    ("라운드랩 독도 토너는", True),
    ("", False),
    (None, False),
])
def test_가리키는_말과_종류_이름뿐이면_어떤_제품인지_알_수_없다(말, 알려_주나):
    assert names_a_product(말) is 알려_주나


def test_되묻는_경우는_셋이다():
    assert needs_clarification(_스펙())                                              # 단서가 없다
    assert needs_clarification(_스펙(request_type=RequestType.BUNDLE, category="skincare"))  # 필수 값이 비었다
    assert needs_clarification(_스펙(request_type=RequestType.EVALUATE,
                                     category="sun", base_product_ref="그 선크림"))   # 어떤 제품인지 모른다
    assert not needs_clarification(_스펙(category="base"))
    assert not needs_clarification(_스펙(request_type=RequestType.EVALUATE,
                                         category="sun", base_product_ref="달바 워터풀 선크림"))


def test_필수_값이_다_찬_세트는_되묻지_않는다():
    세트 = _스펙(request_type=RequestType.BUNDLE, budget=Budget(total=100000),
                 bundle_steps=[BundleStep(category="skincare", product_type="토너", label="토너")])
    assert not needs_clarification(세트)


def test_어떤_제품인지_알_수_없으면_기준_제품을_되물을_필드로_낸다():
    assert missing_fields(_스펙(request_type=RequestType.EVALUATE, base_product_ref="이거")) == ("base_product_ref",)
    # 아예 비었을 때 두 번 넣지 않는다
    assert missing_fields(_스펙(request_type=RequestType.EVALUATE)) == ("base_product_ref",)
    # 평가가 아니면 가리키는 말이어도 묻지 않는다
    assert missing_fields(_스펙(category="base", base_product_ref="이거")) == ()
