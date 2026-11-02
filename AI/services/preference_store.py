"""피드백 반영이 읽고 쓰는 DB 접근.

어떤 값을 만들지는 preference_apply 가 정하고, 여기서는 읽고 쓰기만 한다.
모든 조회와 갱신을 사용자 또는 행 하나로 좁힌다. 조건을 빠뜨린 갱신은 에러 없이
다른 사용자의 값까지 덮는다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

_피드백 = "recommendation_feedback"
_변경 = "preference_weight_changes"
_가중치 = "user_preference_weights"
_job = "recommendation_jobs"


def _db():
    from db.supabase_client import get_supabase

    return get_supabase()


async def load_unapplied_feedback_ids(user_id: str) -> list[int]:
    def _읽기() -> list[dict]:
        return (
            _db().table(_피드백)
            .select("id")
            .eq("user_id", user_id)
            .is_("applied_at", "null")
            .order("id")
            .execute()
        ).data or []

    return [행["id"] for 행 in await asyncio.to_thread(_읽기)]


async def claim_feedback(feedback_id: int, now: datetime) -> dict[str, Any] | None:
    """아직 반영 전일 때만 반영 시각을 채우고 그 행을 돌려준다.

    먼저 읽고 나중에 채우면, 그 사이 사용자가 다시 누른 값을 잃거나 겹친 호출이
    같은 피드백을 두 번 반영한다. 다른 호출이 먼저 가져갔으면 None 이다.
    """
    def _쓰기() -> list[dict]:
        return (
            _db().table(_피드백)
            .update({"applied_at": now.isoformat()})
            .eq("id", feedback_id)
            .is_("applied_at", "null")
            .execute()
        ).data or []

    행 = await asyncio.to_thread(_쓰기)
    return 행[0] if 행 else None


async def release_feedback(feedback_id: int) -> None:
    """반영하지 못한 피드백을 다음 호출이 다시 읽게 한다."""
    def _쓰기() -> None:
        _db().table(_피드백).update({"applied_at": None}).eq("id", feedback_id).execute()

    await asyncio.to_thread(_쓰기)


async def retire_feedback_changes(user_id: str, feedback_id: int, now: datetime) -> None:
    """다시 눌린 피드백의 이전 변경을 합산에서 뺀다."""
    def _쓰기() -> None:
        (
            _db().table(_변경)
            .update({"reverted_at": now.isoformat()})
            .eq("user_id", user_id)
            .eq("source", "FEEDBACK")
            .eq("source_ref", str(feedback_id))
            .is_("reverted_at", "null")
            .execute()
        )

    await asyncio.to_thread(_쓰기)


async def load_job_result(job_id: str) -> dict[str, Any] | None:
    def _읽기() -> list[dict]:
        return (
            _db().table(_job).select("result").eq("id", job_id).limit(1).execute()
        ).data or []

    행 = await asyncio.to_thread(_읽기)
    return 행[0].get("result") if 행 else None


async def insert_change(
    user_id: str, source: str, source_ref: str, deltas: dict[str, float], text: str
) -> None:
    def _쓰기() -> None:
        _db().table(_변경).insert({
            "user_id": user_id,
            "source": source,
            "source_ref": source_ref,
            "deltas": deltas,
            "text": text,
        }).execute()

    await asyncio.to_thread(_쓰기)


async def load_refine_presets_since(user_id: str, since: datetime) -> list[list[str]]:
    """기간 안의 조건 수정에서 고른 선택지를 job 별로 돌려준다."""
    def _읽기() -> list[dict]:
        return (
            _db().table(_job)
            .select("refine_presets")
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .execute()
        ).data or []

    행들 = await asyncio.to_thread(_읽기)
    return [행["refine_presets"] for 행 in 행들 if 행.get("refine_presets")]


async def load_pattern_changes(user_id: str) -> list[dict[str, Any]]:
    def _읽기() -> list[dict]:
        return (
            _db().table(_변경)
            .select("source_ref, reverted_at")
            .eq("user_id", user_id)
            .eq("source", "REFINE_PATTERN")
            .execute()
        ).data or []

    return await asyncio.to_thread(_읽기)


async def load_active_changes(user_id: str) -> list[dict[str, Any]]:
    def _읽기() -> list[dict]:
        return (
            _db().table(_변경)
            .select("source, deltas")
            .eq("user_id", user_id)
            .is_("reverted_at", "null")
            .execute()
        ).data or []

    return await asyncio.to_thread(_읽기)


async def save_weights(
    user_id: str, weights: dict[str, float], source_counts: dict[str, int], now: datetime
) -> None:
    def _쓰기() -> None:
        _db().table(_가중치).upsert({
            "user_id": user_id,
            "weights": weights,
            "source_counts": source_counts,
            "updated_at": now.isoformat(),
        }, on_conflict="user_id").execute()

    await asyncio.to_thread(_쓰기)
