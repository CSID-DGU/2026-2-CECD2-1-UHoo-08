"""홈 맞춤 추천 카드를 저장한다.

사용자, 종류마다 한 줄이고 매일 덮어쓴다(db/migrations/028_home_recommendations.sql).
홈 실행은 recommendation_jobs 에 job 을 만들지 않으므로 job_id 는 비운다.

DB 모듈은 함수 안에서 가져온다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from contracts.internal_api import HomeKind

_TABLE = "home_recommendations"


async def save(user_id: str, kind: HomeKind, result: dict[str, Any]) -> None:
    """(사용자, 종류) 행을 이번 결과로 덮어쓴다."""
    from db.supabase_client import get_supabase

    행 = {
        "user_id": user_id,
        "kind": kind.value,
        "result": result,
        "job_id": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    def _쓰기() -> None:
        get_supabase().table(_TABLE).upsert(행, on_conflict="user_id,kind").execute()

    await asyncio.to_thread(_쓰기)
