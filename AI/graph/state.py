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
    # 상품 상세에서 온 요청의 기준 상품. 있으면 빌더가 Normalize 와 Router 를
    # 건너뛰고 query_spec 의 base_product_ref 로 옮겨 평가 경로를 돈다.
    base_product_id: str | None
    # Normalize 출력. contracts.query_spec.QuerySpec 을 dump 한 dict.
    query_spec: dict
    # Router 출력. graph.registry.SCENARIOS 의 키.
    scenario: str
    # 추천 기준이 되는 사람의 프로필. 기본은 본인,
    # target 이 OTHER 면 화면에서 입력한 다른 사람의 조건이 들어온다.
    user_profile: dict
    target_profile: dict | None
    # 화면에서 고른 추천 기준 탭(SELF, OTHER, POPULAR). 빌더가 관문 뒤에
    # query_spec.target 을 이 값으로 맞춘다. 이후 노드는 query_spec.target 만 본다.
    basis: str

    # ── 컨텍스트 ──────────────────────────────────────────
    # Inventory 가 채운다. 성분은 표준명으로 정규화된 상태다.
    inventory: list[dict]
    # EnvHistory 가 채운다. 4주 누적 요약. 환경을 쓰지 않는 요청이면 None.
    env_summary: dict | None
    # 피드백과 조건 수정 이력에서 나온 사용자별 가중치. Score, PreFilter 가 읽는다.
    weight_prior: dict
    # Coverage 가 쓰고 Retrieve(홈 모드), Compose 가 읽는다.
    # [{key, label, basis, covered, covered_by}]
    env_conditions: list[dict]
    # Budget 이 쓰고 Retrieve(칸별 검색), Bundle 이 읽는다.
    # [{slot_key, label, category, product_type, amount}]
    budget_plan: list[dict]
    # Compatibility 가 쓰고 Alternative(루틴 모드), Compose 가 읽는다.
    # {pairs, counts, schedule, uncompared_count, checked_user_product_ids}
    routine_check: dict
    # Refine 이 쓴다. Retrieve 가 "RESEARCH"(다시 찾기)인지 "RERANK"(부모 후보 재정렬)인지 본다.
    refine_mode: str
    # Refine 이 꺼낸 부모 job 의 result. Rerank 가 순위 변화를 계산할 때 읽는다.
    parent_result: dict

    # ── 후보 흐름 ─────────────────────────────────────────
    intent_vector: list[float]
    # 모양을 항상 같게 유지한다: {product_id, source, similarity, slot_key?}
    # slot_key 는 예산 세트에서 칸별로 찾은 후보에만 있다.
    candidates: list[dict]
    # 후보의 상품 정보. Retrieve, Discovery, Alternative, Collaborative 가 채우고
    # 이후 모든 노드가 읽는다. 같은 상품을 노드마다 다시 조회하지 않으려는 것이다.
    # {product_id: {name, brand, category, image_url, price, original_price,
    #               lowest_price, feature_json, ingredients, average_score, review_count}}
    product_meta: dict
    # PreFilter 가 걸러낸 것. {product_id, reason: OWNED|CONFLICT, detail}
    # 화면에 "보유 제품과 충돌해 N개 제외"로 노출하므로 버리지 않는다.
    excluded: list[dict]
    # PreFilter 가 쓰고 Compose 가 읽는다. 빼지는 않고 배지만 다는 충돌.
    # {product_id: [{user_product_id, name, level: SEPARATE, advice}]}
    conflict_marks: dict
    # PreFilter(상품 평가)가 쓰고 Compose 가 읽는다. 기준 상품은 사용자가 물은
    # 것이라 빼지 않고, 보유 중이거나 충돌한다는 것을 문장으로 알린다.
    base_conflicts: dict
    # Alternative(루틴 모드)가 쓰고 PreFilter, Compose 가 읽는다. 없으면 None.
    # {user_product_id, product_id, name, reason}
    replace_target: dict | None
    # Score 출력. contracts.score.ScoredProduct 참고.
    scored: list[dict]
    alternatives: list[dict]
    # Score(lite)가 점수 미달로 뺀 대체 후보 수. 완료 스냅샷에 남아 BE 가 읽는다.
    alternatives_dropped_count: int
    collaborative: list[dict]
    bundles: list[dict]
    # Bundle 이 채운다. contracts.result.BundleSlot 을 by_alias 로 dump 한 dict.
    # 조합이 달라도 칸별 후보는 같아 job 에 한 벌만 둔다. BE 가 스냅샷에서 읽는다.
    bundle_slots: list[dict]

    # ── 출력 ──────────────────────────────────────────────
    # Compose 출력. contracts.result 의 공통 응답 스키마를 따른다.
    result: dict
    # Clarify 가 채우면 job 이 NEEDS_CLARIFICATION 으로 멈춘다.
    clarify_question: str | None
    # 무엇이 비어서 묻는지. Router 가 쓰고, 되묻는 결과를 만들 때 읽는다.
    clarify_missing_fields: list[str]
    # 되묻기는 1회까지. 답변이 와도 부족하면 그대로 진행한다.
    clarify_count: int
    # 되물은 질문에 대한 사용자의 답. Normalize 가 원래 질의와 함께 읽는다.
    # 원래 질의에 이어 붙이지 않는 이유는, 그러면 화면에 보여줄 질의가
    # 뒤섞이고 무엇이 사용자의 처음 말이었는지 남지 않기 때문이다.
    clarify_answer: str | None
    # 지나간 노드 이름. 디버깅과 플래너가 쓴다.
    trace: list[str]
