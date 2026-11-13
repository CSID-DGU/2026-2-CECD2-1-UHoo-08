"""가중치 결정이 지켜야 할 성질.

피드백으로 쌓인 선호가 요청 때문에 사라지면 안 되고, 불러오지 못한 항목에
가중치가 남으면 안 된다.
"""
import pytest

from contracts.query_spec import QuerySpec, RequestType
from rules.score_weights import DEFAULT_WEIGHTS, decide
from services import preference_apply

_모두 = {
    "budget_fit", "price_value", "review", "personalization",
    "env_fit", "value_signal", "query_fit", "popularity",
}
# B, C 항목이 아직 없을 때
_A만 = _모두 - {"env_fit", "value_signal"}


def _스펙(**값) -> QuerySpec:
    return QuerySpec(request_type=RequestType.SEARCH, **값)


def test_선호_가중치가_없으면_기본_가중치에서_시작한다():
    assert decide(None, _스펙(), "SELF", _모두) == DEFAULT_WEIGHTS
    assert decide({}, _스펙(), "SELF", _모두) == DEFAULT_WEIGHTS


def test_피드백에서_쓰는_기본_가중치와_같다():
    assert preference_apply.기본_가중치 is DEFAULT_WEIGHTS


def test_선호_가중치가_그대로_살아_있다():
    선호 = {**DEFAULT_WEIGHTS, "review": 0.4, "price_value": 0.1}
    결과 = decide(선호, _스펙(), "SELF", _모두)
    assert 결과["review"] == 0.4
    assert 결과["price_value"] == 0.1


def test_점수_항목이_아닌_값은_버린다():
    결과 = decide({"review": 0.3, "모름": 0.9, "similarity": 0.5, "budget_fit": "높음"},
                 _스펙(), "SELF", _모두)
    assert set(결과) == _모두
    assert 결과["review"] == 0.3
    assert 결과["budget_fit"] == 0.0


def test_특징_조건이_있으면_조건_일치를_켠다():
    결과 = decide(None, _스펙(features={"texture": "가벼운"}), "SELF", _모두)
    assert 결과["query_fit"] == 0.3


@pytest.mark.parametrize("선호값, 기대", [(0.0, 0.3), (0.8, 0.8)])
def test_특징_조건은_조건_일치_가중치를_최소값까지_올린다(선호값, 기대):
    결과 = decide({**DEFAULT_WEIGHTS, "query_fit": 선호값},
                 _스펙(features={"texture": "가벼운"}), "SELF", _모두)
    assert 결과["query_fit"] == 기대


@pytest.mark.parametrize("선호값, 기대", [(0.0, 0.25), (0.4, 0.4)])
def test_환경_요청은_환경_가중치를_최소값까지_올린다(선호값, 기대):
    결과 = decide({**DEFAULT_WEIGHTS, "env_fit": 선호값}, _스펙(use_env=True), "SELF", _모두)
    assert 결과["env_fit"] == 기대


@pytest.mark.parametrize("선호값, 기대", [(0.0, 0.3), (0.5, 0.5)])
def test_가성비_요청은_가성비_가중치를_최소값까지_올린다(선호값, 기대):
    결과 = decide({**DEFAULT_WEIGHTS, "value_signal": 선호값},
                 _스펙(value_seeking=True), "SELF", _모두)
    assert 결과["value_signal"] == 기대


def test_가성비_요청이_아니면_피드백으로_올라간_가성비가_남는다():
    결과 = decide({**DEFAULT_WEIGHTS, "value_signal": 0.15}, _스펙(), "SELF", _모두)
    assert 결과["value_signal"] == 0.15


def test_전체_인기_기준이면_개인화를_끄고_인기를_켠다():
    결과 = decide({**DEFAULT_WEIGHTS, "personalization": 0.6}, _스펙(), "POPULAR", _모두)
    assert 결과["personalization"] == 0.0
    assert 결과["popularity"] == 0.35


def test_전체_인기_기준이어도_피드백으로_올라간_인기_가중치는_남는다():
    결과 = decide({**DEFAULT_WEIGHTS, "popularity": 0.5}, _스펙(), "POPULAR", _모두)
    assert 결과["popularity"] == 0.5


def test_불러오지_못한_항목은_0이다():
    결과 = decide(None, _스펙(use_env=True, value_seeking=True), "SELF", _A만)
    assert 결과["env_fit"] == 0.0
    assert 결과["value_signal"] == 0.0
    assert 결과["budget_fit"] == 0.25


def test_플래그를_함께_켜도_서로_덮지_않는다():
    결과 = decide(None, _스펙(features={"finish": "매트"}, use_env=True, value_seeking=True),
                 "POPULAR", _모두)
    assert 결과 == {
        "budget_fit": 0.25, "price_value": 0.25, "review": 0.25, "personalization": 0.0,
        "env_fit": 0.25, "value_signal": 0.3, "query_fit": 0.3, "popularity": 0.35,
    }


def test_0에서_1_사이로_자른다():
    결과 = decide({"review": 1.7, "budget_fit": -0.2}, _스펙(), "SELF", _모두)
    assert 결과["review"] == 1.0
    assert 결과["budget_fit"] == 0.0
