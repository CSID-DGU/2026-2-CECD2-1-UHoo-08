"""요즘 언급이 늘고 있는 상품을 product_trend_daily 에서 읽는다.

추천 결과 카드의 TREND 배지가 쓴다. 최근 며칠의 트렌드 지수 합이 상위권이고 언급이
일정 수 이상인 상품을 고른다. 언급이 몇 건뿐인 상품은 지수가 튀어도 배지를 달지 않는다.

테이블은 C 의 트렌드 집계가 채운다. 비어 있으면 빈 집합이고, 배지를 달지 않는다.
읽기만 한다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을 불러오지도 못한다.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

# 최근 며칠을 보는지, 상위 몇 위까지인지, 언급이 최소 몇 건인지
최근_일수 = 7
상위_순위 = 20
최소_언급 = 3

_페이지_크기 = 1000


def _읽기(시작일: date) -> list[dict[str, Any]]:
    """시작일부터의 행을 모두 읽는다. 기본 상한(1000행)에 잘리지 않게 나눠 읽는다."""
    from db.supabase_client import get_supabase

    행들: list[dict[str, Any]] = []
    시작 = 0
    while True:
        쪽 = (
            get_supabase().table("product_trend_daily")
            .select("product_id, date, mention_count, trend_score")
            .gte("date", 시작일.isoformat())
            .order("date").order("product_id")
            .range(시작, 시작 + _페이지_크기 - 1)
            .execute()
        ).data or []
        if not 쪽:
            return 행들
        행들.extend(쪽)
        시작 += len(쪽)


def rank_trending(
    행들: list[dict[str, Any]], *, top_n: int = 상위_순위, min_mentions: int = 최소_언급,
) -> set[str]:
    """트렌드 지수 합 상위 top_n 안에 들고 언급 합이 min_mentions 이상인 상품."""
    지수: dict[str, float] = defaultdict(float)
    언급: dict[str, int] = defaultdict(int)
    for 행 in 행들:
        pid = 행["product_id"]
        지수[pid] += 행.get("trend_score") or 0.0
        언급[pid] += 행.get("mention_count") or 0
    # 같은 지수면 id 순으로 정해 결과가 흔들리지 않게 한다
    순위 = sorted(지수, key=lambda pid: (-지수[pid], pid))[:top_n]
    return {pid for pid in 순위 if 언급[pid] >= min_mentions}


def get_trending_product_ids(today: date | None = None) -> set[str]:
    오늘 = today or date.today()
    return rank_trending(_읽기(오늘 - timedelta(days=최근_일수 - 1)))
