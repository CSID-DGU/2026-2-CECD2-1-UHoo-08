"""노드 사이를 흐르는 값 전부.

규칙 세 가지다.

1. 노드가 다음 노드에 넘길 값은 전부 여기에 있다. 모듈 전역 dict에 담아
   다음 노드에서 꺼내 쓰지 않는다. 그렇게 하면 같은 요청이 동시에 두 개
   들어올 때 값이 섞이고, 실패했을 때 어디까지 갔는지 남지 않는다.
   기존 ReAct 경로(`agents/tools.py` 의 `_intent_store`)가 아직 그렇게 하고
   있다. 그 경로는 빌더가 S1 을 대체할 때 함께 걷어낸다.
2. `total=False` 다. 노드는 바꾼 키만 담은 dict를 돌려주고, 빌더가 합친다.
3. 키는 snake_case 다. camelCase 는 BE·FE로 나가는 `result` 안에서만 쓴다.
   경계를 섞으면 어느 쪽 이름인지 매번 확인해야 한다.

값을 추가할 때는 어느 노드가 쓰고 어느 노드가 읽는지 주석에 남긴다.
"""
from typing import TypedDict


class GraphState(TypedDict, total=False):
    # ── 입력 ──────────────────────────────────────────────
    job_id: str
    user_id: str
    # 조건 수정(S7)일 때 직전 job. 그 job의 스냅샷에서 후보와 조건을 복원한다.
    parent_job_id: str | None
    raw_query: str
    # Normalize 출력. contracts.query_spec.QuerySpec 을 dump 한 dict.
    query_spec: dict
    # Router 출력. graph.registry.SCENARIOS 의 키.
    scenario: str
    # 추천 기준이 되는 사람의 프로필. 기본은 본인,
    # target 이 OTHER 면 화면에서 입력한 다른 사람의 조건이 들어온다.
    user_profile: dict
    target_profile: dict | None

    # ── 컨텍스트 ──────────────────────────────────────────
    # Inventory 가 채운다. 성분은 표준명으로 정규화된 상태다.
    inventory: list[dict]
    # EnvHistory 가 채운다. 4주 누적 요약. 환경을 쓰지 않는 요청이면 None.
    env_summary: dict | None
    # 피드백과 조건 수정 이력에서 나온 사용자별 가중치. Score 가 읽는다.
    weight_prior: dict

    # ── 후보 흐름 ─────────────────────────────────────────
    intent_vector: list[float]
    # 모양을 항상 같게 유지한다: {product_id, source, similarity}
    candidates: list[dict]
    # PreFilter 가 걸러낸 것. {product_id, reason: OWNED|CONFLICT, detail}
    # 화면에 "보유 제품과 충돌해 N개 제외"로 노출하므로 버리지 않는다.
    excluded: list[dict]
    # Score 출력. contracts.score.ScoredProduct 참고.
    scored: list[dict]
    alternatives: list[dict]
    collaborative: list[dict]
    bundles: list[dict]

    # ── 출력 ──────────────────────────────────────────────
    # Compose 출력. contracts.result 의 공통 응답 스키마를 따른다.
    result: dict
    # Clarify 가 채우면 job 이 NEEDS_CLARIFICATION 으로 멈춘다.
    clarify_question: str | None
    # 되묻기는 1회까지. 답변이 와도 부족하면 그대로 진행한다.
    clarify_count: int
    # 지나간 노드 이름. 디버깅과 플래너가 쓴다.
    trace: list[str]
