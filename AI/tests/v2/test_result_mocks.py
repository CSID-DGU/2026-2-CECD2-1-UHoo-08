"""FE mock 이 결과 스키마와 어긋나지 않는지 검사한다.

mock 을 AI 쪽에 한 벌 더 두지 않고 FE 아래 파일을 그대로 읽는다. 두 벌이면
한쪽만 고쳐져 어긋나고, 그 어긋남은 실연동 붙일 때 발견된다.
"""
import json
import pathlib
import re

import pytest

from contracts.result import BadgeType, RecommendationResult
from contracts.scenario import SCENARIO_NAMES
from graph.registry import SCENARIOS

MOCK_DIR = pathlib.Path(__file__).resolve().parents[3] / "FE" / "src" / "mocks" / "recommendationV2"
MOCK_FILES = sorted(MOCK_DIR.glob("*.json"))


def _읽기(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _모든_키(값, 모음: list[str]) -> list[str]:
    if isinstance(값, dict):
        for 키, 하위 in 값.items():
            모음.append(키)
            _모든_키(하위, 모음)
    elif isinstance(값, list):
        for 하위 in 값:
            _모든_키(하위, 모음)
    return 모음


def test_mock_파일이_있다():
    """FE가 화면을 시작하려면 시나리오별 mock 이 있어야 한다."""
    이름들 = {p.stem for p in MOCK_FILES}
    필요 = {"s1_evaluate", "s2_search", "s6_bundle", "s7_refine",
            "home_routine", "home_env", "clarify"}
    assert 필요 <= 이름들, f"빠진 mock: {필요 - 이름들}"


@pytest.mark.parametrize("path", MOCK_FILES, ids=lambda p: p.stem)
def test_스키마를_통과한다(path):
    RecommendationResult.model_validate(_읽기(path))


@pytest.mark.parametrize("path", MOCK_FILES, ids=lambda p: p.stem)
def test_키가_모두_camelCase다(path):
    """snake_case 키가 섞이면 populate_by_name 때문에 검증은 통과하지만,
    FE는 그 필드를 못 읽는다."""
    밑줄 = sorted({키 for 키 in _모든_키(_읽기(path), []) if "_" in 키})
    assert 밑줄 == [], f"{path.name}: {밑줄}"


@pytest.mark.parametrize("path", MOCK_FILES, ids=lambda p: p.stem)
def test_아는_시나리오다(path):
    assert _읽기(path)["scenario"] in SCENARIOS


@pytest.mark.parametrize("path", MOCK_FILES, ids=lambda p: p.stem)
def test_선택_필드도_빠짐없이_적혀_있다(path):
    """읽어서 다시 쓴 것과 파일이 정확히 같아야 한다.

    mock 은 FE가 타입 검사를 받는 자료이기도 하다. badges 나 reason 처럼
    비어 있어도 되는 필드를 아예 빼면, 파이썬 검증은 기본값으로 통과하지만
    FE는 그 자리에서 undefined 를 받는다."""
    원본 = _읽기(path)
    다시 = RecommendationResult.model_validate(원본).model_dump(mode="json", by_alias=True)
    assert 다시 == 원본


def test_레지스트리와_시나리오_목록이_같다():
    assert set(SCENARIOS) == SCENARIO_NAMES


def test_FE_타입의_시나리오_목록이_같다():
    """FE 유니온이 빠지면 화면이 그 시나리오를 표현할 수 없다."""
    ts = (MOCK_DIR.parents[1] / "api" / "recommendationV2.ts").read_text(encoding="utf-8")
    선언 = ts.split("export type Scenario =", 1)[1].split(";", 1)[0]
    assert set(re.findall(r'"([A-Z0-9_]+)"', 선언)) == SCENARIO_NAMES


def test_모든_배지_종류가_어딘가에_나온다():
    """FE가 배지 종류마다 모양을 잡아야 하므로, mock 에 하나씩은 있어야 한다."""
    나온_것 = set()
    for path in MOCK_FILES:
        결과 = RecommendationResult.model_validate(_읽기(path))
        for 목록 in (결과.items, 결과.alternatives, 결과.similar_user_products):
            for 항목 in 목록:
                나온_것.update(배지.type for 배지 in 항목.badges)
    assert 나온_것 == set(BadgeType), f"mock 에 없는 배지: {set(BadgeType) - 나온_것}"
