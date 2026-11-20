"""Normalize 의 출력 양식 스키마가 지켜야 할 성질.

스키마로 답의 모양을 강제하는 모델은 스키마에 적힌 것만 답할 수 있다. 칸을 빠뜨리면
그 값은 영영 나오지 않는데, 오류 없이 빈 값으로 나와서 알아채기 어렵다.
"""
from contracts.query_spec import QuerySpec
from prompts.product_types_text import QUERY_FEATURES, query_feature_kinds
from prompts.query_normalize import QUERY_SPEC_SCHEMA


def _객체들(조각, 이름="맨 위"):
    """스키마 안의 모든 객체 모양과 그 자리."""
    if isinstance(조각, list):
        for 하나 in 조각:
            yield from _객체들(하나, 이름)
        return
    if not isinstance(조각, dict):
        return
    if 조각.get("type") == "object":
        yield 이름, 조각
    for 말 in ("properties", "$defs"):
        for 칸, 안 in 조각.get(말, {}).items():
            yield from _객체들(안, 칸)
    for 말 in ("items", "anyOf"):
        yield from _객체들(조각.get(말), 이름)


def _모든_말(조각):
    """스키마에 쓰인 말. 칸 이름은 세지 않는다."""
    if isinstance(조각, list):
        for 하나 in 조각:
            yield from _모든_말(하나)
    elif isinstance(조각, dict):
        for 말, 값 in 조각.items():
            yield 말
            if 말 in ("properties", "$defs"):
                for 안 in 값.values():
                    yield from _모든_말(안)
            else:
                yield from _모든_말(값)


def test_특징_표의_글에서_키와_값의_모양을_읽는다():
    모양 = query_feature_kinds()

    assert 모양["product_type"] == "string"
    assert 모양["finish"] == "string"
    assert 모양["skin_concern"] == "array"
    assert 모양["key_ingredient"] == "array"
    assert 모양["white_cast"] == "boolean"
    # 표에 적힌 키가 하나도 빠지지 않는다
    for 줄 in QUERY_FEATURES.values():
        for 조각 in 줄.split("), "):
            assert 조각.split("(")[0].strip() in 모양


def test_특징에는_표의_키를_모두_적는다():
    """키가 정해지지 않은 딕셔너리를 그대로 넘기면 빈 객체만 답할 수 있게 된다."""
    특징 = QUERY_SPEC_SCHEMA["properties"]["features"]

    assert set(특징["properties"]) == set(query_feature_kinds())
    assert 특징["properties"]["product_type"] == {"type": "string"}
    assert 특징["properties"]["skin_concern"] == {"type": "array", "items": {"type": "string"}}
    assert 특징["properties"]["waterproof"] == {"type": "boolean"}


def test_특징의_키는_빼도_되고_나머지_칸은_꼭_적는다():
    스키마 = QUERY_SPEC_SCHEMA

    assert "required" not in 스키마["properties"]["features"]
    assert 스키마["required"] == list(QuerySpec.model_fields)
    assert 스키마["$defs"]["Budget"]["required"] == ["max", "total"]
    assert 스키마["$defs"]["BundleStep"]["required"] == ["category", "product_type", "label"]


def test_모든_객체가_적힌_키만_받는다():
    객체들 = list(_객체들(QUERY_SPEC_SCHEMA))

    assert {이름 for 이름, _ in 객체들} == {"맨 위", "Budget", "BundleStep", "features"}
    assert all(객체["additionalProperties"] is False for _, 객체 in 객체들)


def test_스키마로_강제되지_않는_말은_남기지_않는다():
    쓰인 = set(_모든_말(QUERY_SPEC_SCHEMA))

    assert not 쓰인 & {"title", "description", "default", "exclusiveMinimum", "minLength", "minimum"}


def test_빼도_되는_키와_여러_모양을_받는_칸이_한도_안이다():
    """빼도 되는 키는 24개, 여러 모양을 받는 칸은 16개까지 받아 준다."""
    빼도_되는 = sum(
        len(set(객체.get("properties", {})) - set(객체.get("required", [])))
        for _, 객체 in _객체들(QUERY_SPEC_SCHEMA)
    )
    여러_모양 = sum(말 == "anyOf" for 말 in _모든_말(QUERY_SPEC_SCHEMA))

    assert 빼도_되는 == len(query_feature_kinds()) <= 24
    assert 여러_모양 <= 16


def test_스키마대로_적은_답은_스펙으로_읽힌다():
    답 = {
        "request_type": "BUNDLE", "category": "skincare", "base_product_ref": None,
        "budget": {"max": None, "total": 100000},
        "bundle_steps": [{"category": "skincare", "product_type": "토너", "label": "토너"}],
        "features": {"skin_type": "건성", "skin_concern": ["보습"], "fragrance_free": True},
        "conditions": ["저녁"], "exclude_ingredients": [],
        "target": "SELF", "use_env": False, "value_seeking": True,
    }
    assert set(답) == set(QUERY_SPEC_SCHEMA["required"])

    spec = QuerySpec.model_validate(답)

    assert spec.budget.total == 100000
    assert spec.features == {"skin_type": "건성", "skin_concern": ["보습"], "fragrance_free": True}
