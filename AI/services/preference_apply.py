"""피드백과 반복되는 조건 수정을 사용자 가중치에 반영한다.

신호 하나를 변경 한 건(preference_weight_changes)으로 남기고, 되돌리지 않은
변경을 기본 가중치에 더해 user_preference_weights 를 다시 쓴다. 현재 값을 직접
고치지 않고 매번 다시 계산해야, 되돌릴 때 그 변경만 빠진다.

곱한 값을 쌓지 않고 변화량으로 남기는 것도 같은 이유다. 곱셈은 순서에 따라
값이 달라져 중간의 한 건만 뺄 수 없다.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

from services import preference_store

logger = logging.getLogger(__name__)

# build_score 가 합을 1로 다시 맞추므로 합이 1일 필요는 없다.
# env_fit, value_signal 은 요청에 따라 켜는 항목이라 기본값이 0 이다.
기본_가중치: dict[str, float] = {
    "budget_fit": 0.25,
    "price_value": 0.25,
    "review": 0.25,
    "personalization": 0.25,
    "env_fit": 0.0,
    "value_signal": 0.0,
}

# 항목을 고르지 않은 반응은 이유를 고른 피드백보다 약한 신호로 본다.
_강점_비율 = 0.1
_패턴_횟수 = 3
_패턴_기간 = timedelta(days=30)
# 되돌린 패턴을 다시 만들지 않는 기간. 없으면 다음 호출에서 바로 되살아난다.
_되돌림_유지 = timedelta(days=30)

# 강점 항목을 문장으로 옮길 때 쓰는 이름
_항목_이름 = {
    "budget_fit": "예산",
    "price_value": "가격 대비 가치",
    "review": "후기",
    "personalization": "피부 적합",
}


class _신호(NamedTuple):
    표현: str  # 문장에 들어갈 사용자의 말
    대상: str  # 비중이 오르는 것
    변화량: dict[str, float]


# 이 표에 없는 이유와 선택지는 점수 항목으로 옮길 수 없어 변경을 만들지 않는다.
_이유: dict[str, _신호] = {
    "TOO_EXPENSIVE": _신호("'너무 비싸요'", "가격", {"budget_fit": 0.05, "value_signal": 0.05}),
    "NOT_MY_SKIN": _신호("'내 피부에 안 맞을 것 같아요'", "피부 적합", {"personalization": 0.05}),
    "BAD_REVIEWS": _신호("'후기가 별로예요'", "후기", {"review": 0.05}),
}
_패턴: dict[str, _신호] = {
    "CHEAPER": _신호("'더 저렴하게'를", "가격", {"budget_fit": 0.05, "value_signal": 0.05}),
    "SENSITIVE_OK": _신호("'민감성도 괜찮은'을", "피부 적합", {"personalization": 0.05}),
}

# 같은 사용자의 호출이 겹치면 패턴이 두 건 생기거나 오래된 합계가 나중에 써진다.
_사용자_잠금: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _이유_변경(이유들: list[str]) -> tuple[dict[str, float], str]:
    신호들 = [신호 for 키, 신호 in _이유.items() if 키 in 이유들]
    변화량 = {항목: 값 for 신호 in 신호들 for 항목, 값 in 신호.변화량.items()}
    표현 = ", ".join(신호.표현 for 신호 in 신호들)
    대상 = ", ".join(신호.대상 for 신호 in 신호들)
    return 변화량, f"{표현} 피드백으로 {대상} 비중 ↑"


def _강점_항목(result: dict[str, Any] | None, product_id: str) -> list[str]:
    """그 제품에서 점수가 평균보다 높은 항목. 기본값이 0 인 항목은 움직일 수 없다."""
    for 제품 in (result or {}).get("items") or []:
        if 제품.get("productId") == product_id:
            항목들 = 제품.get("breakdown") or []
            if not 항목들:
                return []
            평균 = sum(항목["score"] for 항목 in 항목들) / len(항목들)
            return [
                항목["key"] for 항목 in 항목들
                if 항목["score"] > 평균 and 기본_가중치.get(항목["key"], 0) > 0
            ]
    return []


def _반응_변경(좋아요: bool, 강점: list[str]) -> tuple[dict[str, float], str]:
    부호 = 1 if 좋아요 else -1
    변화량 = {항목: round(부호 * 기본_가중치[항목] * _강점_비율, 4) for 항목 in 강점}
    표현 = "좋아요" if 좋아요 else "별로예요"
    대상 = ", ".join(_항목_이름.get(항목, 항목) for 항목 in 강점)
    return 변화량, f"'{표현}' 피드백으로 {대상} 비중 {'↑' if 좋아요 else '↓'}"


async def _피드백_한_건(user_id: str, 피드백: dict[str, Any], now: datetime) -> None:
    피드백_id = 피드백["id"]
    # 먼저 빼 두어야, 실패 뒤 다시 돌 때 앞서 들어간 변경과 겹치지 않는다.
    await preference_store.retire_feedback_changes(user_id, 피드백_id, now)

    이유들 = [이유 for 이유 in 피드백.get("reason_tags") or [] if 이유 in _이유]
    좋아요 = 피드백["vote"] == "UP"
    if 이유들 and not 좋아요:
        변화량, 문장 = _이유_변경(이유들)
    else:
        결과 = await preference_store.load_job_result(피드백["job_id"])
        강점 = _강점_항목(결과, 피드백["product_id"])
        if not 강점:
            return
        변화량, 문장 = _반응_변경(좋아요, 강점)

    await preference_store.insert_change(user_id, "FEEDBACK", str(피드백_id), 변화량, 문장)


async def _피드백_반영(user_id: str, now: datetime) -> None:
    for 피드백_id in await preference_store.load_unapplied_feedback_ids(user_id):
        피드백 = await preference_store.claim_feedback(피드백_id, now)
        if 피드백 is None:
            continue

        try:
            await _피드백_한_건(user_id, 피드백, now)
        except Exception:
            # 한 건 때문에 나머지 피드백과 합계까지 멈추지 않게 다음으로 넘어간다.
            logger.exception("피드백 %s 반영 실패. 다음 호출에서 다시 처리한다.", 피드백_id)
            try:
                await preference_store.release_feedback(피드백_id)
            except Exception:
                logger.exception("피드백 %s 의 반영 시각을 되돌리지 못했다.", 피드백_id)


def _다시_만들_수_있나(행들: list[dict[str, Any]], now: datetime) -> bool:
    for 행 in 행들:
        되돌린_때 = 행.get("reverted_at")
        if 되돌린_때 is None:
            return False
        if now - datetime.fromisoformat(되돌린_때) < _되돌림_유지:
            return False
    return True


async def _패턴_반영(user_id: str, now: datetime) -> None:
    고른_것들 = await preference_store.load_refine_presets_since(user_id, now - _패턴_기간)
    # 한 번의 조건 수정에서 같은 선택지는 한 번으로 센다.
    횟수 = Counter(키 for 고른_것 in 고른_것들 for 키 in set(고른_것))

    후보 = [키 for 키 in _패턴 if 횟수[키] >= _패턴_횟수]
    if not 후보:
        return

    기존 = await preference_store.load_pattern_changes(user_id)
    for 키 in 후보:
        if not _다시_만들_수_있나([행 for 행 in 기존 if 행.get("source_ref") == 키], now):
            continue
        신호 = _패턴[키]
        문장 = f"{신호.표현} 자주 고르셔서 {신호.대상} 비중 ↑"
        await preference_store.insert_change(user_id, "REFINE_PATTERN", 키, 신호.변화량, 문장)


def _합산(변경들: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, int]]:
    합: dict[str, float] = dict(기본_가중치)
    for 변경 in 변경들:
        for 항목, 값 in (변경.get("deltas") or {}).items():
            합[항목] = 합.get(항목, 0.0) + 값
    가중치 = {항목: round(min(1.0, max(0.0, 값)), 4) for 항목, 값 in 합.items()}
    신호_수 = {
        "feedback": sum(1 for 변경 in 변경들 if 변경.get("source") == "FEEDBACK"),
        "refine": sum(1 for 변경 in 변경들 if 변경.get("source") == "REFINE_PATTERN"),
    }
    return 가중치, 신호_수


async def apply_feedback(user_id: str, now: datetime | None = None) -> None:
    """이 사용자의 신호를 변경으로 옮기고 가중치를 다시 쓴다.

    중간에 실패해도 반영 전 피드백과 합계는 다음 호출이 이어서 처리한다.
    """
    지금 = now or datetime.now(timezone.utc)
    async with _사용자_잠금[user_id]:
        await _피드백_반영(user_id, 지금)
        await _패턴_반영(user_id, 지금)
        변경들 = await preference_store.load_active_changes(user_id)
        가중치, 신호_수 = _합산(변경들)
        await preference_store.save_weights(user_id, 가중치, 신호_수, 지금)
