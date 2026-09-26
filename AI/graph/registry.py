"""시나리오별 단계 배열과 라우팅 표.

빌더는 이 표만 읽어 StateGraph 를 만든다. 경로를 바꾸는 일이 코드 수정이 아니라
배열 수정이 되게 하려는 것이다. 플래너도 나중에 이 배열을 입력으로 받아
단계를 더하거나 뺀다.

단계 이름 = graph/nodes/ 의 파일 이름 = 그 파일의 함수 이름이다.
"""
from contracts.query_spec import RequestType
from contracts.scenario import Scenario

# 그래프 안에서 쓰는 노드 전부. 여기 없는 이름을 배열에 적으면 테스트가 막는다.
# 오타로 만들어진 단계가 조용히 건너뛰어지는 일을 없애기 위해서다.
KNOWN_NODES: frozenset[str] = frozenset({
    # 공통 관문
    "normalize", "router", "clarify",
    # 후보 만들기
    "retrieve",      # 조건 필터 + 임베딩 검색
    "discovery",     # 기준 상품 해석 (사진·URL·상품명 → 상품)
    "inventory",     # 보유 제품 로드, 성분 표준명 정규화
    "prefilter",     # 보유 제품 제외, 성분 충돌 제외·배지
    # 점수
    "score",         # 가중치 보정까지 하는 전체 계산
    "score_lite",    # prior 만 쓰는 약식 검증. 추가된 후보를 거를 때 쓴다
    # 후보 넓히기
    "alternative",   # 기능이 비슷한 대체 제품
    "collaborative", # 비슷한 조건의 사용자가 고른 제품
    # 조건 수정
    "refine",        # 수정 조건 병합, 재탐색인지 재정렬인지 판단
    "rerank",        # 기존 후보를 다시 정렬만 한다
    # 홈·부품
    "env_history",   # 4주 환경 집계, 제품 조건으로 번역
    "coverage",      # 보유 제품이 환경 조건을 채우는지 판정
    "compatibility", # 보유 제품끼리의 성분 충돌 점검
    "budget",        # 예산·구성 단계 해석
    "bundle",        # 예산 안에서 조합 탐색
    "depletion",     # 소진·변질 시점 예측
    "price",         # 재구매 가격 시점 판단
    # 출구
    "compose",       # 공통 결과 JSON 조립
    "guard",         # 단정·진단성 표현 걸러내기
    "planner",       # 단계 추가·제거 제안
})

# 검색창에서 시작하는 시나리오가 공통으로 거치는 앞단.
# 되묻기(clarify)는 필요할 때만 끼므로 여기 넣지 않는다.
SEARCH_ENTRY: tuple[str, ...] = ("normalize", "router")

# 모든 시나리오의 끝. 결과를 만든 뒤 표현을 검사한다.
COMMON_EXIT: tuple[str, ...] = ("guard",)

SCENARIOS: dict[Scenario, tuple[str, ...]] = {
    # 이 제품 어때? → 평가하고 대체 후보까지
    "S1_EVALUATE": (
        "discovery", "inventory", "prefilter", "score",
        "alternative", "score_lite", "collaborative", "compose",
    ),
    # 조건으로 찾아줘. 가장 많이 쓰이는 경로다.
    # use_env 가 켜지면 빌더가 retrieve 앞에 env_history 를 끼운다.
    "S2_SEARCH": (
        "retrieve", "inventory", "prefilter", "score", "collaborative", "compose",
    ),
    # 이 예산으로 세트 짜줘
    "S6_BUNDLE": (
        "budget", "retrieve", "inventory", "prefilter", "score", "bundle", "compose",
    ),
    # 방금 결과에 조건 추가. 재정렬이 아니라 다시 찾는다.
    "S7_REFINE": (
        "refine", "retrieve", "inventory", "prefilter", "score", "compose",
    ),
    # 홈 — 보유 제품끼리 충돌하면 알려주고 대체 제품을 추천
    "HOME_ROUTINE": (
        "inventory", "compatibility", "alternative", "prefilter", "score_lite", "compose",
    ),
    # 홈 — 4주 환경에 견줘 부족한 기능을 채울 제품을 추천
    "HOME_ENV": (
        "env_history", "inventory", "coverage", "retrieve", "prefilter",
        "score_lite", "compose",
    ),
    # 소진·재구매. 여유가 있을 때 붙인다.
    "S4_REPLENISH": (
        "depletion", "price", "retrieve", "inventory", "prefilter",
        "score", "alternative", "compose",
    ),
}

# 홈은 검색창을 거치지 않는다. 배치가 직접 시나리오를 지정해 돌린다.
HOME_SCENARIOS: frozenset[Scenario] = frozenset({"HOME_ROUTINE", "HOME_ENV"})

# 요청 유형 하나가 시나리오 하나로 간다. 같은 질문이 매번 같은 곳으로 가야
# 하므로 LLM이 아니라 이 표가 정한다.
ROUTE: dict[RequestType, Scenario] = {
    RequestType.SEARCH: "S2_SEARCH",
    RequestType.EVALUATE: "S1_EVALUATE",
    RequestType.BUNDLE: "S6_BUNDLE",
    RequestType.REFINE: "S7_REFINE",
}


def full_path(scenario: str) -> tuple[str, ...]:
    """빌더가 실제로 조립할 단계 전부."""
    if scenario not in SCENARIOS:
        raise KeyError(f"모르는 시나리오: {scenario}")
    앞단 = () if scenario in HOME_SCENARIOS else SEARCH_ENTRY
    return 앞단 + SCENARIOS[scenario] + COMMON_EXIT
