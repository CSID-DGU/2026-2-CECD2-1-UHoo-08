"""가중치 보정이 지켜야 할 성질.

LLM 이 엉뚱한 값을 줘도 선호와 요청 조건으로 정한 가중치가 망가지면 안 된다.
"""
import json

import pytest

from prompts.weight_adjustment_v2 import build_weight_adjustment_v2_user_prompt
from services.weight_validator import validate_multipliers

_키 = ["budget_fit", "review", "personalization"]


def test_범위_안의_배수는_그대로_쓴다():
    assert validate_multipliers(
        {"budget_fit": 0.5, "review": 2.0, "personalization": 1.3}, _키,
    ) == {"budget_fit": 0.5, "review": 2.0, "personalization": 1.3}


@pytest.mark.parametrize("값", [0.49, 2.01, -1, 0, "1.5", None, True, [1.2]])
def test_이상한_배수는_1로_본다(값):
    결과 = validate_multipliers({"budget_fit": 값, "review": 1.5}, _키)
    assert 결과["budget_fit"] == 1.0
    # 한 항목이 이상해도 다른 항목의 보정은 살린다
    assert 결과["review"] == 1.5


@pytest.mark.parametrize("원본", [None, "review: 2", [1.5], 3])
def test_JSON_객체가_아니면_모두_1이다(원본):
    assert validate_multipliers(원본, _키) == {키: 1.0 for 키 in _키}


def test_모르는_항목은_버리고_빠진_항목은_1이다():
    결과 = validate_multipliers({"review": 1.2, "env_fit": 2.0, "모름": 1.5}, _키)
    assert 결과 == {"budget_fit": 1.0, "review": 1.2, "personalization": 1.0}


def test_프롬프트에는_켜진_항목만_보인다():
    문장 = build_weight_adjustment_v2_user_prompt(
        {"budget_fit": 0.25, "review": 0.4, "env_fit": 0.0},
        "GIFT", ["친구 생일"], value_seeking=False,
    )
    첫줄 = 문장.splitlines()[0].removeprefix("켜진 점수 항목: ")
    켜진 = json.loads(첫줄)
    assert set(켜진) == {"budget_fit", "review"}
    assert 켜진["review"] == {"이름": "후기 일치", "가중치": 0.4}
    assert "GIFT" in 문장
    assert "친구 생일" in 문장


def test_검색_목적이_없으면_없음으로_적는다():
    문장 = build_weight_adjustment_v2_user_prompt({"review": 0.25}, None, [], value_seeking=True)
    assert "검색 목적: 없음" in 문장
    assert "가성비 요청: 예" in 문장
