"""시나리오 배열이 지켜야 할 성질.

배열은 사람이 손으로 고치는 값이라 오타와 순서 실수가 난다. 그런데 그 실수가
런타임에서는 "단계가 조용히 건너뛰어짐" 이나 "빈 후보로 0점" 처럼 결과만
이상한 모습으로 나타난다. 여기서 먼저 막는다.
"""
import pytest

from contracts.query_spec import RequestType
from graph.registry import (
    COMMON_EXIT,
    HOME_SCENARIOS,
    KNOWN_NODES,
    ROUTE,
    SCENARIOS,
    SEARCH_ENTRY,
    full_path,
)

시나리오_목록 = sorted(SCENARIOS)


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_모르는_단계_이름이_없다(시나리오):
    """이름이 곧 파일명이라, 오타는 없는 파일을 가리킨다.

    빌더가 실제로 조립하는 건 full_path 다. SCENARIOS 만 보면 공통
    앞단·뒷단의 오타를 놓친다."""
    모르는 = [단계 for 단계 in full_path(시나리오) if 단계 not in KNOWN_NODES]
    assert 모르는 == [], f"{시나리오}: {모르는}"


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_같은_단계를_연달아_두지_않는다(시나리오):
    단계들 = SCENARIOS[시나리오]
    연달아 = [a for a, b in zip(단계들, 단계들[1:]) if a == b]
    assert 연달아 == [], f"{시나리오}: {연달아}"


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_prefilter_앞에_inventory가_있다(시나리오):
    """PreFilter 는 보유 제품을 읽는다. 앞에 Inventory 가 없으면 아무것도
    걸러내지 못한 채 통과해, 이미 가진 제품이 그대로 추천된다."""
    단계들 = SCENARIOS[시나리오]
    if "prefilter" not in 단계들:
        pytest.skip("이 시나리오는 걸러낼 후보가 없다")
    assert "inventory" in 단계들[: 단계들.index("prefilter")], f"{시나리오}: inventory 누락"


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_점수_앞에_후보를_만드는_단계가_있다(시나리오):
    """후보가 비면 점수는 예외 없이 빈 결과를 낸다. 화면에는 '추천 없음'으로
    보여서 원인을 찾기 어렵다."""
    후보_생성 = {"retrieve", "discovery", "alternative", "inventory"}
    단계들 = SCENARIOS[시나리오]
    for 점수 in ("score", "score_lite"):
        if 점수 in 단계들:
            앞 = set(단계들[: 단계들.index(점수)])
            assert 앞 & 후보_생성, f"{시나리오}: {점수} 앞에 후보를 만드는 단계가 없다"


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_compose로_끝난다(시나리오):
    assert SCENARIOS[시나리오][-1] == "compose", f"{시나리오}: 결과를 만들지 않고 끝난다"


def test_모든_요청_유형이_시나리오로_간다():
    """유형을 추가하고 라우팅 표를 빠뜨리면 그 질의가 갈 곳을 잃는다."""
    assert set(ROUTE) == set(RequestType)
    assert set(ROUTE.values()) <= set(SCENARIOS)


def test_홈_시나리오는_실제로_존재한다():
    assert HOME_SCENARIOS <= set(SCENARIOS)


def test_검색_경로는_관문을_거치고_홈은_거치지_않는다():
    검색 = full_path("S2_SEARCH")
    홈 = full_path("HOME_ENV")
    assert 검색[: len(SEARCH_ENTRY)] == SEARCH_ENTRY
    assert "normalize" not in 홈 and "router" not in 홈


@pytest.mark.parametrize("시나리오", 시나리오_목록)
def test_전체_경로는_guard로_끝난다(시나리오):
    assert full_path(시나리오)[-len(COMMON_EXIT):] == COMMON_EXIT


def test_모르는_시나리오는_예외다():
    with pytest.raises(KeyError):
        full_path("S9_NOPE")
