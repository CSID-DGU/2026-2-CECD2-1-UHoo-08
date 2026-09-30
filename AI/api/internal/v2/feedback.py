"""피드백을 반영해 사용자 가중치 prior 를 다시 계산한다."""
import logging

from fastapi import APIRouter, status

from contracts.internal_api import Accepted, FeedbackApplyRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feedback/apply", status_code=status.HTTP_202_ACCEPTED)
async def feedback_apply(req: FeedbackApplyRequest) -> Accepted:
    # TODO: recommendation_feedback 의 이유 태그를 점수 항목별로 역산해
    #       user_preference_weights 를 갱신한다.
    logger.warning("stub: /feedback/apply user=%s", req.user_id)
    return Accepted(stub=True)
