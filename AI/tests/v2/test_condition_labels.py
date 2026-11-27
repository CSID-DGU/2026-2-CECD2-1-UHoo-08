"""질의 요약이 지켜야 할 성질.

조건 수정 화면의 칩으로 그대로 나가므로 짧고 사람이 읽는 말이어야 한다.
"""
import pytest

from contracts.query_spec import Budget, QuerySpec, RequestType, Target
from rules.condition_labels import feature_labels, summarize


@pytest.mark.parametrize("키, 값, 기대", [
    ("product_type", "쿠션", ["쿠션"]),
    ("finish", "세미매트", ["세미매트"]),
    ("coverage", "높음", ["커버력 높음"]),
    ("lasting_power", "중간", ["지속력 중간"]),
    ("texture", "가벼운", ["가벼운 제형"]),
    ("skin_type", "건성", ["건성 피부"]),
    ("skin_concern", ["모공", "잡티"], ["모공", "잡티"]),
    ("personal_color", "웜톤", ["웜톤"]),
    ("fragrance_free", True, ["무향"]),
    ("fragrance_free", False, []),
    ("white_cast", False, ["백탁 없음"]),
    ("white_cast", True, []),
    ("moisturizing", True, ["보습"]),
    ("moisturizing", False, []),
    ("key_ingredient", ["나이아신아마이드", "판테놀"], ["나이아신아마이드", "판테놀"]),
    ("모르는_키", "값", ["값"]),
    ("finish", None, []),
])
def test_특징을_읽는_말로_바꾼다(키, 값, 기대):
    assert feature_labels({키: 값}) == 기대


def test_같은_말은_한_번만_남긴다():
    assert feature_labels({"skin_concern": ["모공", "모공"], "finish": "매트"}) == ["모공", "매트"]


def test_특징_뒤에_문장_조건을_잇고_예산은_넣지_않는다():
    spec = QuerySpec(
        request_type=RequestType.SEARCH, category="base",
        features={"finish": "매트", "product_type": "쿠션"},
        conditions=["여름", " ", "매트"],
        budget=Budget(max=30000), target=Target.SELF,
    )
    요약 = summarize(spec, "여름 가벼운 매트 쿠션 3만원 이하")
    assert 요약.conditions == ["매트", "쿠션", "여름"]
    assert 요약.budget_max == 30000
    assert 요약.model_dump(mode="json", by_alias=True) == {
        "raw": "여름 가벼운 매트 쿠션 3만원 이하", "category": "base",
        "conditions": ["매트", "쿠션", "여름"], "budgetMax": 30000, "budgetTotal": None,
        "target": "SELF", "useEnv": False, "valueSeeking": False,
    }


def test_원문이_없으면_빈_문자열이다():
    요약 = summarize(QuerySpec(request_type=RequestType.SEARCH, use_env=True), None)
    assert 요약.raw == ""
    assert 요약.use_env is True
