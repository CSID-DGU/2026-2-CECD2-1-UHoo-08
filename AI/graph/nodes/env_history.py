"""사용자 지역의 최근 4주 환경을 모아 요즘 필요한 기능을 정한다. 판정은 rules/env_needs.py.

READS:  user_profile
WRITES: env_summary

    {region, period_start, period_end, day_count, stats, needs: [{key, label, basis,
     reason_text, category, features, conditions}]}

Coverage 가 needs 를 보유 제품과 견주고, Retrieve 가 덮이지 않은 기능의 상품을 찾고,
Compose 가 ENV 배지와 카드 이유를 단다.

지역을 정하지 않은 사용자는 needs 가 빈 요약이다. 홈 배치는 지역이 있는 사용자만 부르지만,
조건 탐색의 "요즘 날씨에 맞는" 요청은 누구나 할 수 있다.

기간은 오늘(KST)을 포함한 28일이다. BE 환경 요약(EnvironmentService.PERIOD_DAYS)과 같다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from graph.state import GraphState
from rules.env_needs import summarize

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
PERIOD_DAYS = 28


def _rows(region: str, start: date, end: date) -> list[dict]:
    from db.env_reader import get_env_daily
    return get_env_daily(region, start, end)


def period(today: date) -> tuple[date, date]:
    return today - timedelta(days=PERIOD_DAYS - 1), today


async def env_history(state: GraphState) -> dict:
    region = (state.get("user_profile") or {}).get("region")
    start, end = period(datetime.now(KST).date())
    if not region:
        logger.info("env_history: 지역이 없어 환경을 보지 않는다.")
        return {"env_summary": summarize(None, [], start, end)}

    rows = await asyncio.to_thread(_rows, region, start, end)
    요약 = summarize(region, rows, start, end)
    logger.info("env_history: %s 관측 %d일, 필요한 기능 %s",
                region, 요약["day_count"], [n["key"] for n in 요약["needs"]] or "없음")
    return {"env_summary": 요약}
