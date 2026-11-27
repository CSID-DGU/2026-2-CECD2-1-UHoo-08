"""지역별 하루 환경 집계(env_daily) 읽기. EnvHistory 노드 전용."""
from __future__ import annotations

from datetime import date
from typing import Any

from db.supabase_client import get_supabase

_COLUMNS = (
    "date, temp_avg, temp_min, temp_max, humidity_avg, uv_max, "
    "pm10_avg, pm25_avg, sample_count"
)


def get_env_daily(region: str, start: date, end: date) -> list[dict[str, Any]]:
    """region 의 start ~ end(포함) 하루 집계. 날짜 순."""
    return (
        get_supabase().table("env_daily")
        .select(_COLUMNS)
        .eq("region", region)
        .gte("date", start.isoformat())
        .lte("date", end.isoformat())
        .order("date")
        .execute()
    ).data or []
