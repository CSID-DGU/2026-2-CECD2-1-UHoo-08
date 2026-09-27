"""홈 맞춤 추천 카드 생성. 사용자별 일일 배치가 부른다."""
import logging

from fastapi import APIRouter, status

from contracts.internal_api import Accepted, HomeRunRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/home/run", status_code=status.HTTP_202_ACCEPTED)
async def home_run(req: HomeRunRequest) -> Accepted:
    # TODO: HOME_ROUTINE · HOME_ENV 경로를 돌려 home_recommendations 에 넣는다.
    logger.warning("stub: /home/run user=%s kind=%s", req.user_id, req.kind.value)
    return Accepted(stub=True)
