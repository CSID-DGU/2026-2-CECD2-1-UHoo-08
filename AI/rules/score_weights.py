"""점수 항목별 가중치를 정한다.

사용자의 선호 가중치(피드백으로 쌓인 값)에서 시작해, 이번 요청이 무엇을 따지는지에
맞춰 고친다. 합을 1로 맞추는 일은 build_score 가 한다. 그래서 여기서는 항목끼리의
비율만 신경 쓴다.

요청 플래그가 켜는 항목은 선호 가중치보다 작아지지 않게 한다. 피드백으로 올라간
값이 요청 때문에 도로 내려가면 피드백이 반영되지 않은 것처럼 보인다.
"""
from __future__ import annotations

from contracts.query_spec import QuerySpec, Target
from contracts.score import SCORE_LABELS

# 사용자 선호 가중치가 없을 때 쓰는 값. build_score 가 합을 1로 맞추므로 합이 1일
# 필요는 없다. env_fit, value_signal, query_fit, popularity 는 요청에 따라 켜는
# 항목이라 0 이다.
DEFAULT_WEIGHTS: dict[str, float] = {
    "budget_fit": 0.25,
    "price_value": 0.25,
    "review": 0.25,
    "personalization": 0.25,
    "env_fit": 0.0,
    "value_signal": 0.0,
    "query_fit": 0.0,
    "popularity": 0.0,
}

# 요청 플래그가 켜는 항목의 가중치
조건_일치_가중치 = 0.3
환경_최소_가중치 = 0.25
가성비_최소_가중치 = 0.3
인기_가중치 = 0.35

# 총점에 섞는 항목. similarity 는 대체 후보 화면에 보여 주는 이름일 뿐이다.
_점수_키 = frozenset(SCORE_LABELS) - {"similarity"}


def decide(
    prior: dict | None,
    spec: QuerySpec,
    basis: str,
    active: set[str],
) -> dict[str, float]:
    """이번 요청의 항목별 가중치. 값은 0~1 이다.

    prior    사용자 선호 가중치. 없으면 DEFAULT_WEIGHTS
    basis    추천 기준(SELF, OTHER, POPULAR)
    active   이번에 불러온 점수 항목. 여기에 없는 항목은 0 이다
    """
    시작 = prior if prior else DEFAULT_WEIGHTS
    가중치: dict[str, float] = {
        키: float(값) for 키, 값 in 시작.items()
        if 키 in _점수_키 and isinstance(값, (int, float)) and not isinstance(값, bool)
    }

    if spec.features:
        가중치["query_fit"] = 조건_일치_가중치
    if spec.use_env:
        가중치["env_fit"] = max(가중치.get("env_fit", 0.0), 환경_최소_가중치)
    if spec.value_seeking:
        가중치["value_signal"] = max(가중치.get("value_signal", 0.0), 가성비_최소_가중치)
    if basis == Target.POPULAR:
        # 전체 인기 기준이면 개인 프로필을 따지지 않는다
        가중치["personalization"] = 0.0
        가중치["popularity"] = 인기_가중치

    return {
        키: (min(1.0, max(0.0, 가중치.get(키, 0.0))) if 키 in active else 0.0)
        for 키 in sorted(_점수_키)
    }
