"""날씨를 볼 지역을 정한다. 요청에 지역이 없으면 그 사용자가 설정한 지역을 쓴다.

앱의 홈 환경 카드와 환경 화면은 user_id 만 보내고 지역은 보내지 않는다. 지역을
보내지 않았다고 기본 지역(인천)을 쓰면, 사용자가 지역을 바꿔도 화면이 계속 인천을 보여 준다.

    1. 요청에 region 이 있으면 그 지역
    2. 없고 user_id 가 있으면 users.region (BE 가 지역 설정 때 저장한다)
    3. 그것도 없거나 모르는 지역이면 기본 지역

키오스크는 user_id 없이 부르므로 지금처럼 기본 지역이다.
users.region 은 BE SupportedRegion 값이고 weather.REGIONS 의 키와 같다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없는 CI 에서 이 모듈을 시험할 수 없다.
"""
from __future__ import annotations

import logging
from typing import Callable, Container, Optional

logger = logging.getLogger(__name__)


def _users_region(user_id: str) -> Optional[str]:
    from db.supabase_client import get_supabase

    rows = (get_supabase().table("users").select("region").eq("id", user_id)
            .limit(1).execute()).data or []
    return (rows[0].get("region") if rows else None) or None


def resolve(
    region: Optional[str],
    user_id: Optional[str],
    *,
    known: Container[str],
    default: str,
    lookup: Callable[[str], Optional[str]] = _users_region,
) -> str:
    """위 순서대로 고른 지역. 사용자 지역을 읽다 실패해도 날씨 화면은 떠야 하므로 기본 지역으로 둔다."""
    if region and region.strip():
        return region.strip()
    if user_id:
        try:
            저장된 = lookup(user_id)
        except Exception:
            logger.exception("사용자 지역 조회 실패 user_id=%s. 기본 지역을 쓴다.", user_id)
            저장된 = None
        if 저장된 in known:
            return 저장된
        if 저장된:
            logger.warning("모르는 사용자 지역 %r user_id=%s. 기본 지역을 쓴다.", 저장된, user_id)
    return default
