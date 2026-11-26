"""홈 맞춤 추천 카드 생성. 사용자별 일일 배치가 부른다.

비동기다. 결과는 응답이 아니라 home_recommendations 로 간다. 그 경로에 꼭 필요한 단계가
아직 없으면 돌리지 않고 stub 으로 응답한다. BE 가 경고 로그를 남긴다.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, status

from contracts.internal_api import Accepted, HomeRunRequest
from services import home_runner

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/home/run", status_code=status.HTTP_202_ACCEPTED)
async def home_run(req: HomeRunRequest, tasks: BackgroundTasks) -> Accepted:
    빠진 = home_runner.missing_nodes(req.kind)
    if 빠진:
        logger.warning("stub: /home/run user=%s kind=%s 아직 없는 단계 %s",
                       req.user_id, req.kind.value, 빠진)
        return Accepted(stub=True)
    tasks.add_task(home_runner.run, req.user_id, req.kind)
    return Accepted()
