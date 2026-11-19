"""부족한 기능 확인 단계가 지켜야 할 성질.

보유 제품이 이미 채우는 기능까지 추천하면 홈 카드가 "이미 있는 것을 또 사라" 고 말한다.
"""
import pytest

from graph.nodes.coverage import coverage

_자외선 = {"key": "UV_PROTECT", "label": "자외선 차단", "basis": "자외선 지수 6 이상 22일",
          "reason_text": "요즘 자외선이 강해요", "category": "sun",
          "features": {"product_type": "선크림"}, "conditions": ["자외선 차단"]}
_진정 = {"key": "SOOTHING", "label": "진정", "basis": "미세먼지 나쁨 14일",
        "reason_text": "요즘 미세먼지가 많아요", "category": "skincare",
        "features": {"product_type": "토너"}, "conditions": ["진정"]}
_선크림 = {"user_product_id": "up1", "product_id": "s1", "name": "닥터지 선크림",
          "category": "sun", "feature_json": {"product_type": "선크림"}}


def _상태(needs, inventory=None, **값):
    상태 = {"env_summary": {"region": "서울", "day_count": 28, "needs": needs},
            "query_spec": {"request_type": "SEARCH", "target": "SELF"}, **값}
    if inventory is not None:
        상태["inventory"] = inventory
    return 상태


@pytest.mark.asyncio
async def test_보유_제품이_채우는_기능은_덮였다고_적고_나머지로_검색_조건을_만든다():
    나옴 = await coverage(_상태([_자외선, _진정], [_선크림]))
    assert 나옴["env_conditions"] == [
        {"key": "UV_PROTECT", "label": "자외선 차단", "basis": "자외선 지수 6 이상 22일",
         "covered": True, "covered_by": "닥터지 선크림"},
        {"key": "SOOTHING", "label": "진정", "basis": "미세먼지 나쁨 14일",
         "covered": False, "covered_by": None},
    ]
    spec = 나옴["query_spec"]
    assert spec["use_env"] is True and spec["category"] == "skincare"
    assert spec["conditions"] == ["진정(스킨케어)"] and spec["target"] == "SELF"


@pytest.mark.asyncio
async def test_카테고리나_특징이_다르면_채우지_않는다():
    다른_종류 = {**_선크림, "feature_json": {"product_type": "선스틱"}}
    다른_카테고리 = {**_선크림, "category": "base"}
    나옴 = await coverage(_상태([_자외선], [다른_종류, 다른_카테고리]))
    assert 나옴["env_conditions"][0]["covered"] is False
    assert 나옴["query_spec"]["category"] == "sun"
    assert 나옴["query_spec"]["conditions"] == ["자외선 차단(선케어)"]


@pytest.mark.asyncio
async def test_보유_제품_단계가_없으면_모두_덮이지_않은_것으로_본다(caplog):
    나옴 = await coverage(_상태([_자외선, _진정]))
    assert [c["covered"] for c in 나옴["env_conditions"]] == [False, False]
    # 덮이지 않은 기능마다 기능 이름과 카테고리를 짝지어 조건을 만든다
    assert 나옴["query_spec"]["conditions"] == ["자외선 차단(선케어)", "진정(스킨케어)"]
    # 카테고리가 섞여 있으면 질의의 카테고리는 비운다
    assert 나옴["query_spec"]["category"] is None
    assert "보유 제품 단계가 아직 없다" in caplog.text


@pytest.mark.asyncio
async def test_필요한_기능이_없으면_조건은_빈_목록이다():
    나옴 = await coverage(_상태([], [_선크림]))
    assert 나옴["env_conditions"] == []
    assert 나옴["query_spec"]["conditions"] == [] and 나옴["query_spec"]["use_env"] is True


@pytest.mark.asyncio
async def test_모두_덮였으면_검색_조건이_비고_카테고리는_그대로다():
    나옴 = await coverage(_상태([_자외선], [_선크림]))
    assert 나옴["env_conditions"][0]["covered"] is True
    assert 나옴["query_spec"]["conditions"] == []
    assert "category" not in 나옴["query_spec"]


@pytest.mark.asyncio
async def test_카테고리가_없는_기능은_이름만_조건으로_쓴다():
    나옴 = await coverage(_상태([{**_진정, "category": None}], []))
    assert 나옴["query_spec"]["conditions"] == ["진정"]
