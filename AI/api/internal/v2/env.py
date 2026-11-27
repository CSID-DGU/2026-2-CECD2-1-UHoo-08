"""지역별 실외 환경 수집을 지금 바로 한 번 돌린다.

평소에는 앱 안의 매시 스케줄이 돈다(services/env_collector.run_schedule).
이 경로는 배포 직후 확인이나 놓친 시간을 채울 때 손으로 부른다.
같은 시간을 다시 넣어도 지역마다 한 줄이라 여러 번 불러도 괜찮다.
"""
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class EnvCollectResponse(BaseModel):
    collected_at: str
    saved: list[str]          # 저장한 지역
    skipped: list[str]        # 값을 하나도 못 받아 건너뛴 지역
    air_regions: int          # 에어코리아에서 받은 시·도 수
    refreshed_days: list[str]  # 다시 집계한 "지역 날짜"


@router.post("/env/collect", tags=["env"])
async def env_collect() -> EnvCollectResponse:
    # 키와 DB 가 있어야 하는 모듈이라 함수 안에서 가져온다(패키지 규칙)
    from services.env_collector import collect_once

    return EnvCollectResponse(**await asyncio.to_thread(collect_once))
