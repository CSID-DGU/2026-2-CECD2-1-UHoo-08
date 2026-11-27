"""시나리오 골든셋의 기대 성질을 추천 결과에 대어 본다.

합성 데이터에는 정답 순위가 사실상 없다. 그래서 순위를 맞추게 하지 않고 결과가 지켜야
할 성질을 본다. 보유 제품이 빠졌는지, 상위 결과가 조건을 지키는지, 기준에 맞는 점수
항목이 쓰였는지 같은 것이다.

결과는 Compose 가 만든 camelCase dict 이다. 결과 카드에는 카테고리와 제품 종류가 없어서
그래프 상태의 상품 정보(product_meta)를 함께 받는다.

판정은 성질 하나마다 (통과 여부, 설명) 이다. 설명은 실패했을 때 리포트에 그대로 싣는다.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic.alias_generators import to_camel

from rules.product_types import matches, product_types

# 상위 몇 개를 보는지
상위_수 = 5
# 홈 루틴 판정 자료를 상품 정보에 넣어 넘기는 키. 러너가 채운다(eval/run_scenario_eval.py).
# {"product_of": {user_product_id: product_id}, "avoid_with": {product_id: [user_product_id]} | None}
ROUTINE_KEY = "_routine"

Judgement = tuple[bool, str]


def _카드들(결과: dict) -> list[dict]:
    return 결과.get("items") or []


def _상위(결과: dict) -> list[dict]:
    return _카드들(결과)[:상위_수]


def must_exclude(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """결과 카드에 없어야 하는 상품."""
    남은 = sorted({c["productId"] for c in _카드들(결과)} & set(기대))
    return (not 남은, f"결과에 남아 있다: {남은}" if 남은 else "")


def must_exclude_reason(기대: dict[str, str], 결과: dict, 메타: dict) -> Judgement:
    """제외 목록에 그 사유로 있어야 하는 상품."""
    실제 = {e["productId"]: e["reason"] for e in 결과.get("excluded") or []}
    틀린 = {pid: 실제.get(pid) for pid, 사유 in 기대.items() if 실제.get(pid) != 사유}
    return (not 틀린, f"제외 사유가 다르다(기대와 다른 실제 값): {틀린}" if 틀린 else "")


def top5_all(기대: dict[str, Any], 결과: dict, 메타: dict) -> Judgement:
    """상위 5개가 모두 카테고리, 가격 상한, 제품 종류를 만족한다. 결과가 비면 실패다."""
    상위 = _상위(결과)
    if not 상위:
        return False, "결과 카드가 없다"
    어긴: list[str] = []
    for 카드 in 상위:
        pid = 카드["productId"]
        정보 = 메타.get(pid) or {}
        if "category" in 기대 and 정보.get("category") != 기대["category"]:
            어긴.append(f"{pid} 카테고리 {정보.get('category')}")
        if "price_max" in 기대 and (카드.get("price") is None or 카드["price"] > 기대["price_max"]):
            어긴.append(f"{pid} 가격 {카드.get('price')}")
        if "product_type" in 기대:
            특징 = 정보.get("feature_json") or {}
            종류들 = product_types(특징)
            # 종류를 모르는 상품도 어긴 것으로 본다. 필터는 남기지만 순위가 낮아져야 한다
            if not matches(기대["product_type"], 종류들, 기대.get("category")):
                어긴.append(f"{pid} 제품 종류 {특징.get('product_type')}")
    return (not 어긴, ", ".join(어긴))


def _첫_항목들(결과: dict) -> set[str] | None:
    카드들 = _카드들(결과)
    if not 카드들:
        return None
    return {항목["key"] for 항목 in 카드들[0].get("breakdown") or []}


def breakdown_has(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """상위 1개의 점수 분해에 그 항목이 있다."""
    항목 = _첫_항목들(결과)
    if 항목 is None:
        return False, "결과 카드가 없다"
    빠진 = sorted(set(기대) - 항목)
    return (not 빠진, f"점수 항목이 없다: {빠진}" if 빠진 else "")


def breakdown_lacks(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """상위 1개의 점수 분해에 그 항목이 없다."""
    항목 = _첫_항목들(결과)
    if 항목 is None:
        return False, "결과 카드가 없다"
    있는 = sorted(set(기대) & 항목)
    return (not 있는, f"없어야 할 점수 항목이 있다: {있는}" if 있는 else "")


def badge_any(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """상위 5개 중 하나에 그 종류의 배지가 하나라도 있다."""
    있는 = {배지["type"] for 카드 in _상위(결과) for 배지 in 카드.get("badges") or []}
    return (bool(있는 & set(기대)), f"상위 {상위_수}개의 배지: {sorted(있는)}")


def non_empty(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """그 필드가 비어 있지 않다. 필드 이름은 snake_case 로 적어도 된다."""
    빈 = [필드 for 필드 in 기대 if not 결과.get(to_camel(필드), 결과.get(필드))]
    return (not 빈, f"비어 있다: {빈}" if 빈 else "")


def alternatives_min_score(기대: int, 결과: dict, 메타: dict) -> Judgement:
    """대체 후보가 모두 이 점수 이상이다. 대체 후보가 있는지는 non_empty 로 본다."""
    낮은 = [(a["productId"], a["totalScore"]) for a in 결과.get("alternatives") or []
            if a["totalScore"] < 기대]
    return (not 낮은, f"하한보다 낮다: {낮은}" if 낮은 else "")


def change_present(기대: bool, 결과: dict, 메타: dict) -> Judgement:
    """조건 수정 결과 카드에 순위 변화가 있다(true) 또는 없다(false). 결과가 비면 실패다."""
    카드들 = _카드들(결과)
    if not 카드들:
        return False, "결과 카드가 없다"
    빈 = [카드["productId"] for 카드 in 카드들 if not 카드.get("change")]
    if 기대:
        return (not 빈, f"순위 변화가 없는 카드: {빈}" if 빈 else "")
    있는 = [카드["productId"] for 카드 in 카드들 if 카드.get("change")]
    return (not 있는, f"순위 변화가 있는 카드: {있는}" if 있는 else "")


def conditions_cover(기대: dict[str, bool], 결과: dict, 메타: dict) -> Judgement:
    """홈 환경 결과의 필요한 기능마다 보유 제품이 채웠는지(covered). 기능 목록도 같아야 한다.

    conditions 가 없거나 null 이면 실패다. null 은 분석 전이고 빈 목록은 분석했지만 필요한
    기능이 없다는 뜻이라, 둘을 같게 보면 분석 전 결과가 "필요한 기능 없음"으로 통과한다.
    """
    조건들 = 결과.get("conditions")
    if not isinstance(조건들, list):
        return False, f"conditions 가 목록이 아니다: {조건들!r}"
    실제 = {c["key"]: c.get("covered") for c in 조건들}
    if set(실제) != set(기대):
        return False, f"기능 목록이 다르다: 기대 {sorted(기대)} / 실제 {sorted(실제)}"
    틀린 = {키: 실제[키] for 키, 값 in 기대.items() if 실제[키] is not 값}
    return (not 틀린, f"덮였는지가 다르다(실제 값): {틀린}" if 틀린 else "")


def items_empty(기대: bool, 결과: dict, 메타: dict) -> Judgement:
    """결과 카드가 비어 있다(true) 또는 있다(false). 홈 환경에서 모두 덮였을 때 쓴다."""
    수 = len(_카드들(결과))
    return ((수 == 0) is 기대, f"결과 카드 {수}개")


def replace_target_in(기대: list[str], 결과: dict, 메타: dict) -> Judgement:
    """홈 루틴의 바꿀 제품이 이 상품 중 하나다. 빈 목록이면 바꿀 제품이 없어야 한다."""
    대체 = 결과.get("replacement")
    if not 기대:
        return (대체 is None, f"바꿀 제품이 있다: {대체['replaceTarget']}" if 대체 else "")
    if not 대체:
        return False, "바꿀 제품이 없다"
    upid = 대체["replaceTarget"]["userProductId"]
    pid = ((메타.get(ROUTINE_KEY) or {}).get("product_of") or {}).get(upid)
    return (pid in 기대, f"바꿀 제품 {대체['replaceTarget']['name']} ({pid})")


def replacement_items_no_avoid(기대: bool, 결과: dict, 메타: dict) -> Judgement:
    """대체 후보가 남은 보유 제품과 함께 쓰지 않는 게 좋은 조합이 아니다. 성분 부품이 없으면 실패다."""
    상대 = (메타.get(ROUTINE_KEY) or {}).get("avoid_with")
    if 상대 is None:
        return False, "성분 부품(B)이 없어 판정할 수 없다"
    걸린 = {pid: upids for pid, upids in 상대.items() if upids}
    return ((not 걸린) is 기대, f"AVOID 인 대체 후보: {걸린}" if 걸린 else "AVOID 인 대체 후보가 없다")


CHECKS: dict[str, Callable[[Any, dict, dict], Judgement]] = {
    "must_exclude": must_exclude,
    "must_exclude_reason": must_exclude_reason,
    "top5_all": top5_all,
    "breakdown_has": breakdown_has,
    "breakdown_lacks": breakdown_lacks,
    "badge_any": badge_any,
    "non_empty": non_empty,
    "alternatives_min_score": alternatives_min_score,
    "change_present": change_present,
    "conditions_cover": conditions_cover,
    "items_empty": items_empty,
    "replace_target_in": replace_target_in,
    "replacement_items_no_avoid": replacement_items_no_avoid,
}
PROPERTY_KEYS: frozenset[str] = frozenset(CHECKS)


def judge(기대: dict[str, Any], 결과: dict, 메타: dict) -> dict[str, Judgement]:
    """기대 성질마다 판정한다. 모르는 키는 실패로 둔다(데이터 검증이 먼저 잡는다)."""
    판정: dict[str, Judgement] = {}
    for 키, 값 in 기대.items():
        판정함수 = CHECKS.get(키)
        판정[키] = 판정함수(값, 결과, 메타) if 판정함수 else (False, f"모르는 성질: {키}")
    return 판정
