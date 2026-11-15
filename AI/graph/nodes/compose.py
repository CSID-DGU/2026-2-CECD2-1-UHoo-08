"""그래프 상태로 화면에 보낼 추천 결과를 만든다.

READS:  scenario, job_id, user_id, raw_query, query_spec, user_profile, inventory, scored,
        product_meta, excluded, conflict_marks, env_summary, collaborative, bundles, trace,
        base_product_id, base_conflicts, alternatives, rank_changes, env_conditions, candidates
WRITES: result

결과 모양은 contracts.result.RecommendationResult 다. BE 가 그대로 저장하고 FE 가 그린다.

먼저 꼭 있어야 하는 부품이 실제로 돌았는지 본다. 아직 없는 노드는 빌더가 그냥
흘려보내므로, 확인하지 않으면 예산 세트 요청이 조합 없이 "완료" 로 나간다. 사용자는
"추천할 것이 없다" 로 읽는다. 그런 경로는 실패로 남긴다.

    결과 카드       점수 상위 10개
    배지            카드마다 최대 2개. 시간대 나눠 쓰기, 환경, 가성비, 요즘 언급 순
    추천 이유       카드 10개를 LLM 한 번으로. 실패하거나 빠진 카드는 점수가 높은 두 항목으로 만든 문장
    제외 목록       거른 후보와 이유
    비슷한 사람들   만족도를 점수 자리에 둔다

상품 평가는 결과 카드가 기준 상품 하나다. 이미 쓰고 있거나 함께 쓰면 안 되는 보유
제품이 있으면 그 내용을 이유 문장 앞에 둔다. 시간대만 나누면 되는 충돌은 배지로 단다.
대체 후보는 간단 채점(score_lite)이 매긴 점수 그대로 카드로 만든다.

조건 수정은 조건 탐색과 같은 모양에 카드마다 이전 결과와 비교한 순위 변화를 싣는다.
질의 요약은 합친 질의로 만들고, 원문은 이번에 보낸 문장이다.

홈 환경 카드는 요즘 환경에 필요한 기능마다 보유 제품이 채웠는지를 싣고, 덮이지 않은
기능마다 그 기능을 채우라고 찾은 상품 중 점수 상위 3개를 기능 순서대로 묶어 싣는다.
카드마다 그 기능의 문구를 환경 배지로 달아, 어느 기능의 추천인지 알 수 있게 한다.
필요한 기능이 없으면 조건은 빈 목록이다. 모든 기능이 덮였으면 카드가 없고, BE 가
"모두 갖췄어요" 로 보여 준다.

홈 루틴 카드는 분석 칸 없이 나가면 카드가 계속 분석 전으로 보이므로, 분기를 더하기
전에는 실패로 남긴다.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from contracts.query_spec import QuerySpec, RequestType
from contracts.result import (
    Badge,
    BadgeType,
    BundleOption,
    EnvCondition,
    ExcludedItem,
    RankChange,
    RecommendationResult,
    ResultItem,
)
from contracts.score import SCORE_LABELS, ScoreContext
from graph.state import GraphState
from rules.condition_labels import summarize
from rules.env_match import meets
from rules.guard_rules import fallback_reason
from rules.prefilter import 보유_문구, 시간대_나눔, 함께_쓰지_않음

logger = logging.getLogger(__name__)

# 결과 카드 수
카드_수 = 10
# 홈 환경 카드에서 덮이지 않은 기능 하나에 싣는 상품 수
기능별_카드_수 = 3
# 카드 하나에 다는 배지 수
배지_상한 = 2
# 환경, 가성비 배지를 다는 항목 점수
배지_점수_기준 = 70
요즘_언급_문구 = "요즘 언급이 늘고 있어요"
# 이유 문장 LLM 응답을 기다리는 최대 시간(초). 넘기면 규칙 문장으로 채운다.
이유_LLM_제한_초 = 15.0

# 이 단계가 아직 없으면(stub) 결과를 만들 수 없는 경로
REQUIRED_NODES: dict[str, tuple[str, ...]] = {
    "S6_BUNDLE": ("budget", "bundle"),
    "HOME_ENV": ("env_history",),
    "HOME_ROUTINE": ("compatibility",),
}
_세트_경로 = "S6_BUNDLE"
_상품_평가 = "S1_EVALUATE"
_조건_탐색 = "S2_SEARCH"
_조건_수정 = "S7_REFINE"
_홈_환경 = "HOME_ENV"
# 홈 카드에서만 채우는 칸. 비어 있으면 싣지 않는다. 검색 결과에 홈 칸이 null 로
# 실려 있으면 BE 의 예시 결과와 모양이 달라진다.
_홈_칸 = frozenset({
    "conditions", "counts", "pairs", "replacement", "schedule",
    "uncompared_count", "checked_user_product_ids",
})
# 분석 칸(counts, pairs 등)을 채우는 분기가 아직 없는 경로
_홈_경로 = frozenset({"HOME_ROUTINE"})
_가성비_모듈 = "scorers.value_signal"


class 부품_없음(RuntimeError):
    """꼭 필요한 단계가 아직 없어 결과를 만들 수 없다."""


def _부품을_확인한다(시나리오: str, 자취: list[str]) -> None:
    빠진 = [이름 for 이름 in REQUIRED_NODES.get(시나리오, ()) if f"{이름}(stub)" in 자취]
    if 빠진:
        raise 부품_없음(f"{시나리오}: 아직 없는 단계가 있어 결과를 만들 수 없다 {빠진}")
    if 시나리오 in _홈_경로:
        raise 부품_없음(f"{시나리오}: 홈 결과를 조립하는 단계가 아직 없다")
    if "inventory(stub)" in 자취:
        logger.warning("compose: 보유 제품 단계가 아직 없다. 보유 제품을 거르지 못한 결과다.")


def _스펙(state: GraphState) -> QuerySpec:
    return QuerySpec.model_validate(
        {"request_type": RequestType.SEARCH.value, **(state.get("query_spec") or {})}
    )


def _점수(점수표: dict, 키: str) -> float | None:
    for 항목 in 점수표.get("breakdown") or []:
        if 항목["key"] == 키:
            return 항목["score"]
    return None


def rule_reason(점수표: dict) -> str | None:
    """점수가 높은 두 항목으로 만든 이유 문장. 항목이 없으면 None."""
    return fallback_reason(점수표.get("breakdown") or [])


def _이유_입력(s: dict, 메타: dict, 배지: list[Badge]) -> dict:
    항목들 = sorted(s.get("breakdown") or [], key=lambda 항목: 항목["score"], reverse=True)[:2]
    return {
        "product_id": s["product_id"],
        "name": 메타.get("name") or "",
        "top_items": [
            {"label": SCORE_LABELS.get(항목["key"], 항목["label"]), "score": round(항목["score"])}
            for 항목 in 항목들
        ],
        "badges": [b.text for b in 배지],
    }


async def _llm_이유(
    조건: list[str], 상위: list[dict], 메타: dict, 배지: dict[str, list[Badge]],
) -> dict[str, str]:
    """카드마다 LLM 이 쓴 이유 문장. 검증을 통과한 것만 돌려준다.

    JSON 이 아니거나, 문장이 아니거나, 너무 길거나, 호출이 실패하면 그 카드는 빠진다.
    빠진 카드는 부른 쪽이 규칙 문장으로 채운다.
    """
    from prompts.reason_compose import (
        REASON_COMPOSE_SYSTEM,
        build_reason_compose_user_prompt,
        이유_최대_글자,
    )

    카드들 = [
        _이유_입력(s, 메타[s["product_id"]], 배지.get(s["product_id"], []))
        for s in 상위 if s.get("breakdown")
    ]
    if not 카드들:
        return {}
    # 쓸 카드가 있을 때만 LLM 모듈을 불러온다. 결과가 비었는데 LLM SDK 까지
    # 불러오면 SDK 가 없는 환경(가벼운 CI)에서 빈 결과 조립이 실패한다.
    from services.llm import LLMRole, get_llm
    try:
        원본 = await get_llm(LLMRole.COMPOSE).chat_json(
            system=REASON_COMPOSE_SYSTEM,
            user=build_reason_compose_user_prompt(조건, 카드들),
            timeout=이유_LLM_제한_초,
        )
    except Exception:
        logger.warning("compose: 이유 문장 LLM 호출 실패. 규칙 문장으로 채운다.", exc_info=True)
        return {}
    if not isinstance(원본, dict):
        logger.warning("compose: 이유 문장 LLM 응답이 JSON 객체가 아니다. 규칙 문장으로 채운다.")
        return {}

    이유: dict[str, str] = {}
    for 카드 in 카드들:
        문장 = 원본.get(카드["product_id"])
        if isinstance(문장, str) and 0 < len(문장.strip()) <= 이유_최대_글자:
            이유[카드["product_id"]] = 문장.strip()
    if len(이유) < len(카드들):
        logger.info("compose: 이유 문장 %d개 중 %d개를 규칙 문장으로 채운다.",
                    len(카드들), len(카드들) - len(이유))
    return 이유


async def _요즘_언급(상품_ids: list[str]) -> set[str]:
    """요즘 언급이 늘고 있는 상품. 읽지 못하면 배지를 달지 않고 넘어간다."""
    if not 상품_ids:
        return set()
    from db.trend_reader import get_trending_product_ids

    try:
        return await asyncio.to_thread(get_trending_product_ids) & set(상품_ids)
    except Exception:
        logger.warning("compose: 트렌드를 읽지 못했다. 요즘 언급 배지를 달지 않는다.", exc_info=True)
        return set()


async def _가성비_문구(state: GraphState, spec: QuerySpec, 상품들: list[dict]) -> dict[str, str]:
    """가성비 점수 항목의 설명 함수가 있으면 그 문구. 없으면 빈 dict."""
    if not 상품들:
        return {}
    try:
        모듈 = importlib.import_module(_가성비_모듈)
    except ModuleNotFoundError as e:
        if e.name != _가성비_모듈:
            raise
        return {}
    설명 = getattr(모듈, "explain", None)
    if 설명 is None:
        return {}
    ctx = ScoreContext(
        job_id=state["job_id"], user_id=state["user_id"], query_spec=spec,
        user_profile=state.get("user_profile") or {},
        inventory=state.get("inventory") or [],
        env_summary=state.get("env_summary"),
    )
    return await 설명(상품들, ctx) or {}


def _환경_문구(필요들: list[dict], 메타: dict) -> str | None:
    for 필요 in 필요들:
        if 필요.get("reason_text") and meets(필요, 메타):
            return 필요["reason_text"]
    return None


def _덮이지_않은_필요(state: GraphState) -> list[dict]:
    덮인 = {조건["key"] for 조건 in state.get("env_conditions") or [] if 조건.get("covered")}
    return [
        필요 for 필요 in (state.get("env_summary") or {}).get("needs") or []
        if 필요.get("key") not in 덮인
    ]


def _찾은_기능(state: GraphState) -> dict[str, dict]:
    """홈 환경 후보마다 그 후보를 찾은 덮이지 않은 기능. retrieve 홈 모드가 출처에 적는다."""
    필요들 = {f"env:{필요['key']}": 필요 for 필요 in _덮이지_않은_필요(state)}
    return {
        후보["product_id"]: 필요들[후보.get("source")]
        for 후보 in state.get("candidates") or [] if 후보.get("source") in 필요들
    }


def _기능별_상위(state: GraphState) -> list[dict]:
    """덮이지 않은 기능 순서대로, 기능마다 점수 상위 몇 개를 이어 붙인다."""
    찾은 = _찾은_기능(state)
    메타 = state.get("product_meta") or {}
    상위: list[dict] = []
    for 필요 in _덮이지_않은_필요(state):
        상위 += [
            s for s in state.get("scored") or []
            if s["product_id"] in 메타 and 찾은.get(s["product_id"]) is 필요
        ][:기능별_카드_수]
    return 상위


async def _배지들(
    state: GraphState, spec: QuerySpec, 상위: list[dict], 메타: dict,
) -> dict[str, list[Badge]]:
    # 홈 환경 카드는 덮이지 않은 기능을 채우라고 찾은 상품이라 환경 점수와 상관없이
    # 그 기능의 문구를 단다. 조건 탐색은 환경 점수가 높은 상품에만 요즘 필요한 기능 문구를 단다.
    홈_환경 = state.get("scenario") == _홈_환경
    찾은 = _찾은_기능(state) if 홈_환경 else {}
    환경_필요들 = (state.get("env_summary") or {}).get("needs") or []
    상품_ids = [s["product_id"] for s in 상위]
    가성비_대상 = [
        {**메타[s["product_id"]], "product_id": s["product_id"]} for s in 상위
        if (_점수(s, "value_signal") or 0) >= 배지_점수_기준
    ]
    요즘, 가성비 = await asyncio.gather(
        _요즘_언급(상품_ids), _가성비_문구(state, spec, 가성비_대상),
    )
    충돌 = state.get("conflict_marks") or {}

    배지: dict[str, list[Badge]] = {}
    for s in 상위:
        pid = s["product_id"]
        후보: list[Badge] = []
        for 표시 in 충돌.get(pid) or []:
            if 표시.get("advice"):
                후보.append(Badge(type=BadgeType.CONFLICT_SEPARATE, text=표시["advice"]))
                break
        if 홈_환경 or (_점수(s, "env_fit") or 0) >= 배지_점수_기준:
            문구 = (
                (찾은.get(pid) or {}).get("reason_text") if 홈_환경
                else _환경_문구(환경_필요들, 메타[pid])
            )
            if 문구:
                후보.append(Badge(type=BadgeType.ENV, text=문구))
        if 가성비.get(pid):
            후보.append(Badge(type=BadgeType.VALUE, text=가성비[pid]))
        if pid in 요즘:
            후보.append(Badge(type=BadgeType.TREND, text=요즘_언급_문구))
        배지[pid] = 후보[:배지_상한]
    return 배지


def _카드(pid: str, 메타: dict, total: int, **값: Any) -> ResultItem:
    return ResultItem(
        product_id=pid,
        name=메타.get("name") or "",
        brand=메타.get("brand") or "",
        image_url=메타.get("image_url"),
        price=메타.get("price"),
        total_score=total,
        **값,
    )


async def _결과_카드(
    state: GraphState, spec: QuerySpec, 조건: list[str], 개수: int = 카드_수,
) -> list[ResultItem]:
    메타 = state.get("product_meta") or {}
    상위 = []
    for s in state.get("scored") or []:
        if s["product_id"] not in 메타:
            logger.warning("compose: %s 의 상품 정보가 없어 카드에서 뺀다.", s["product_id"])
            continue
        상위.append(s)
        if len(상위) == 개수:
            break

    배지 = await _배지들(state, spec, 상위, 메타)
    # 배지 문구를 이유 문장의 재료로 쓰므로 배지를 먼저 단다
    이유 = await _llm_이유(조건, 상위, 메타, 배지)
    return [
        _카드(
            s["product_id"], 메타[s["product_id"]], s["total"],
            breakdown=s.get("breakdown") or [],
            badges=배지.get(s["product_id"], []),
            reason=이유.get(s["product_id"]) or rule_reason(s),
        )
        for s in 상위
    ]


def _기준_앞_문장(판정: dict) -> str | None:
    """기준 상품의 이유 문장 앞에 둘 말. 보유가 충돌보다 먼저다."""
    if 판정.get("owned"):
        return 보유_문구
    for 표시 in 판정.get("conflicts") or []:
        if 표시.get("level") == 함께_쓰지_않음 and 표시.get("advice"):
            return 표시["advice"]
    return None


async def _기준_카드(state: GraphState, spec: QuerySpec, 조건: list[str]) -> list[ResultItem]:
    """상품 평가의 결과 카드. 기준 상품 하나다."""
    기준 = state.get("base_product_id")
    판정 = (state.get("base_conflicts") or {}).get(기준) or {}
    나눌 = [표시 for 표시 in 판정.get("conflicts") or [] if 표시.get("level") == 시간대_나눔]
    기준_상태: dict = {
        **state,
        "scored": [s for s in state.get("scored") or [] if s["product_id"] == 기준][:1],
    }
    if 나눌:
        기준_상태["conflict_marks"] = {**(state.get("conflict_marks") or {}), 기준: 나눌}

    카드들 = await _결과_카드(기준_상태, spec, 조건)
    앞 = _기준_앞_문장(판정)
    if not 앞:
        return 카드들
    return [
        카드.model_copy(update={"reason": f"{앞}. {카드.reason}" if 카드.reason else 앞})
        for 카드 in 카드들
    ]


def _대체_카드(state: GraphState) -> list[ResultItem]:
    """대체 후보 카드. 시간대를 나눠 쓸 보유 제품이 있으면 배지를 단다."""
    메타 = state.get("product_meta") or {}
    충돌 = state.get("conflict_marks") or {}
    카드들: list[ResultItem] = []
    for a in state.get("alternatives") or []:
        pid = a["product_id"]
        if pid not in 메타:
            logger.warning("compose: 대체 후보 %s 의 상품 정보가 없어 뺀다.", pid)
            continue
        배지 = [
            Badge(type=BadgeType.CONFLICT_SEPARATE, text=표시["advice"])
            for 표시 in 충돌.get(pid) or [] if 표시.get("advice")
        ][:1]
        카드들.append(_카드(pid, 메타[pid], a["total"], breakdown=a.get("breakdown") or [], badges=배지))
    return 카드들


def _순위_변화(카드들: list[ResultItem], 변화: dict[str, dict]) -> list[ResultItem]:
    """조건 수정 카드에 순위 변화를 싣는다. 변화를 모르는 카드는 비워 둔다."""
    나감 = []
    for 카드 in 카드들:
        값 = 변화.get(카드.product_id) or {}
        나감.append(카드.model_copy(update={
            "change": RankChange(값["change"]) if 값.get("change") else None,
            "rank_delta": 값.get("rank_delta"),
        }))
    return 나감


def _제외(state: GraphState) -> list[ExcludedItem]:
    메타 = state.get("product_meta") or {}
    return [
        ExcludedItem(
            product_id=e["product_id"],
            name=e.get("name") or (메타.get(e["product_id"]) or {}).get("name"),
            reason=e["reason"],
            detail=e.get("detail"),
        )
        for e in state.get("excluded") or []
    ]


def _비슷한_사람들(state: GraphState) -> list[ResultItem]:
    메타 = state.get("product_meta") or {}
    return [
        _카드(c["product_id"], 메타[c["product_id"]], c["satisfaction_percent"])
        for c in state.get("collaborative") or []
        if c["product_id"] in 메타
    ]


async def compose(state: GraphState) -> dict:
    시나리오 = state["scenario"]
    _부품을_확인한다(시나리오, state.get("trace") or [])
    spec = _스펙(state)
    요약 = summarize(spec, state.get("raw_query"))

    if 시나리오 == _세트_경로:
        요약 = 요약.model_copy(update={"conditions": [단계.label for 단계 in spec.bundle_steps]})
        결과 = RecommendationResult(
            job_id=state["job_id"], scenario=시나리오, query=요약,
            bundles=[BundleOption.model_validate(b) for b in state.get("bundles") or []],
            excluded=_제외(state),
        )
    elif 시나리오 == _홈_환경:
        상위 = _기능별_상위(state)
        결과 = RecommendationResult(
            job_id=state["job_id"], scenario=시나리오, query=요약,
            items=await _결과_카드({**state, "scored": 상위}, spec, 요약.conditions, len(상위)),
            excluded=_제외(state),
            conditions=[EnvCondition.model_validate(c) for c in state.get("env_conditions") or []],
        )
    elif 시나리오 == _상품_평가:
        결과 = RecommendationResult(
            job_id=state["job_id"], scenario=시나리오, query=요약,
            items=await _기준_카드(state, spec, 요약.conditions),
            alternatives=_대체_카드(state),
            similar_user_products=_비슷한_사람들(state),
            excluded=_제외(state),
        )
    else:
        카드들 = await _결과_카드(state, spec, 요약.conditions)
        if 시나리오 == _조건_수정:
            카드들 = _순위_변화(카드들, state.get("rank_changes") or {})
        결과 = RecommendationResult(
            job_id=state["job_id"], scenario=시나리오, query=요약,
            items=카드들,
            similar_user_products=_비슷한_사람들(state),
            excluded=_제외(state),
        )
    비운_칸 = {칸 for 칸 in _홈_칸 if getattr(결과, 칸) is None}
    # 되묻기 칸은 조건 탐색 예시에만 null 로 실려 있다. 다른 경로는 비어 있으면 싣지 않는다
    if 시나리오 != _조건_탐색 and 결과.clarify is None:
        비운_칸.add("clarify")
    return {"result": 결과.model_dump(mode="json", by_alias=True, exclude=비운_칸)}
