"""시나리오 이름.

레지스트리(`graph/registry.py`)와 결과 스키마(`contracts/result.py`)와
FE 타입이 같은 목록을 봐야 한다. 이름을 여기 한 곳에 두고, 레지스트리가
이 목록과 맞는지는 테스트가 검사한다.
"""
from typing import Literal, get_args

Scenario = Literal[
    "S1_EVALUATE",
    "S2_SEARCH",
    "S6_BUNDLE",
    "S7_REFINE",
    "HOME_ROUTINE",
    "HOME_ENV",
    "S4_REPLENISH",
]

SCENARIO_NAMES: frozenset[str] = frozenset(get_args(Scenario))
