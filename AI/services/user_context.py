"""추천을 돌리기 전에 사용자 맥락을 채운다.

BE 의 추천 요청에는 사용자 프로필이 없다. 노드가 읽을 프로필과 선호 가중치를
그래프를 돌리기 전에 한 번 읽어 상태에 넣는다. 노드마다 따로 읽으면 같은
사용자를 여러 번 조회하고, 추천 기준(본인, 다른 사람, 전체 인기)에 따라 무엇을
읽을지도 노드마다 다시 정하게 된다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from contracts.query_spec import Target
from services.preference_apply import 기본_가중치

logger = logging.getLogger(__name__)

# 노드가 읽는 프로필 칸. users 의 컬럼 이름과 같다.
_프로필_칸 = (
    "skin_type", "skin_concerns", "personal_color", "region",
    "search_purpose", "price_tolerance_percent",
)
# 다른 사람 기준일 때 화면에서 오는 값(camelCase) → 프로필 칸
_받을_사람_칸 = {
    "skinType": "skin_type",
    "skinConcerns": "skin_concerns",
    "personalColor": "personal_color",
    "relation": "relation",
}


def _빈_프로필() -> dict[str, Any]:
    프로필: dict[str, Any] = {칸: None for 칸 in _프로필_칸}
    프로필["skin_concerns"] = []
    return 프로필


def _db():
    from db.supabase_client import get_supabase

    return get_supabase()


async def _본인_프로필(user_id: str) -> dict[str, Any]:
    def _읽기() -> list[dict]:
        return (
            _db().table("users")
            .select(", ".join(_프로필_칸))
            .eq("id", user_id)
            .limit(1)
            .execute()
        ).data or []

    행 = await asyncio.to_thread(_읽기)
    프로필 = _빈_프로필()
    if not 행:
        logger.warning("사용자 %s 를 찾지 못했다. 빈 프로필로 진행한다.", user_id)
        return 프로필
    for 칸 in _프로필_칸:
        if 행[0].get(칸) is not None:
            프로필[칸] = 행[0][칸]
    return 프로필


def _받을_사람_프로필(target_profile: dict | None) -> dict[str, Any]:
    """화면에서 입력한 다른 사람의 조건을 프로필 모양으로 옮긴다.

    지역은 비워 둔다. 받을 사람이 어디에 사는지 모르므로 요청한 사람의
    지역 환경을 쓰면 틀린 추천이 된다.
    """
    프로필 = _빈_프로필()
    프로필["relation"] = None
    if not target_profile:
        logger.warning("다른 사람 기준인데 조건이 비어 있다. 빈 프로필로 진행한다.")
        return 프로필
    for 화면_칸, 칸 in _받을_사람_칸.items():
        if target_profile.get(화면_칸) is not None:
            프로필[칸] = target_profile[화면_칸]
    return 프로필


async def _선호_가중치(user_id: str) -> dict[str, float]:
    """피드백과 조건 수정 이력으로 만든 가중치. 없으면 기본 가중치."""
    def _읽기() -> list[dict]:
        return (
            _db().table("user_preference_weights")
            .select("weights")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        ).data or []

    행 = await asyncio.to_thread(_읽기)
    if not 행 or not 행[0].get("weights"):
        return dict(기본_가중치)
    return dict(행[0]["weights"])


async def load(user_id: str, basis: str, target_profile: dict | None) -> dict[str, Any]:
    """{"user_profile": {...}, "weight_prior": {...}} 를 돌려준다.

    가중치는 추천 기준과 상관없이 요청한 사람의 것이다. 어떤 기준을 중요하게
    보는지는 요청한 사람의 취향이기 때문이다.
    """
    if basis == Target.OTHER.value:
        프로필 = _받을_사람_프로필(target_profile)
    else:
        프로필 = await _본인_프로필(user_id)
    return {"user_profile": 프로필, "weight_prior": await _선호_가중치(user_id)}
