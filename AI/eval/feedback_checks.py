"""피드백 반영 골든셋의 기대 성질을 판정한다.

같은 질의를 기본 가중치로 돌린 결과(기본)와 피드백을 반영한 가중치로 돌린 결과(바뀐)를
나란히 놓고 본다. 결과는 Compose 가 만든 camelCase dict 다.

판정은 성질 하나마다 (통과 여부, 설명) 이다.
"""
from __future__ import annotations

import statistics
from typing import Any, Callable

Judgement = tuple[bool, str]


def _카드들(결과: dict) -> list[dict]:
    return 결과.get("items") or []


def _순위(결과: dict) -> dict[str, int]:
    return {카드["productId"]: i for i, 카드 in enumerate(_카드들(결과), start=1)}


def _평균_순위(결과: dict, 상품들: set[str]) -> float:
    """결과에 없는 상품은 마지막 다음 순위로 본다. 빠진 것도 내려간 것이다."""
    순위 = _순위(결과)
    없음 = len(_카드들(결과)) + 1
    return statistics.mean(순위.get(pid, 없음) for pid in 상품들)


def cheaper_rank_up(기대: bool, 기본: dict, 바뀐: dict) -> Judgement:
    """기본 결과에서 가격이 중앙값 이하인 상품의 평균 순위가 피드백 뒤 오른다."""
    가격 = {카드["productId"]: 카드["price"] for 카드 in _카드들(기본) if 카드.get("price")}
    if len(가격) < 2:
        return False, "기본 결과에 가격이 있는 카드가 2개보다 적다"
    중앙값 = statistics.median(가격.values())
    싼 = {pid for pid, p in 가격.items() if p <= 중앙값}
    전, 후 = _평균_순위(기본, 싼), _평균_순위(바뀐, 싼)
    올랐다 = 후 < 전
    설명 = f"저렴한 상품 {len(싼)}개의 평균 순위 {전:.2f} → {후:.2f}"
    return (올랐다 == 기대, "" if 올랐다 == 기대 else 설명)


def revert_restores(기대: bool, 기본: dict, 바뀐: dict) -> Judgement:
    """피드백을 모두 되돌린 뒤의 결과 카드 순서가 기본 결과와 같다."""
    전 = [카드["productId"] for 카드 in _카드들(기본)]
    후 = [카드["productId"] for 카드 in _카드들(바뀐)]
    같다 = bool(전) and 전 == 후
    return (같다 == 기대, "" if 같다 == 기대 else f"기본 {전[:5]} / 되돌린 뒤 {후[:5]}")


CHECKS: dict[str, Callable[[Any, dict, dict], Judgement]] = {
    "cheaper_rank_up": cheaper_rank_up,
    "revert_restores": revert_restores,
}
PROPERTY_KEYS: frozenset[str] = frozenset(CHECKS)


def judge(기대: dict[str, Any], 기본: dict, 바뀐: dict) -> dict[str, Judgement]:
    판정: dict[str, Judgement] = {}
    for 키, 값 in 기대.items():
        판정함수 = CHECKS.get(키)
        판정[키] = 판정함수(값, 기본, 바뀐) if 판정함수 else (False, f"모르는 성질: {키}")
    return 판정
