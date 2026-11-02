"""피드백을 반영해 사용자 가중치를 다시 계산한다.

비동기다. 결과는 응답이 아니라 user_preference_weights 로 간다.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, status

from contracts.internal_api import Accepted, FeedbackApplyRequest
from services import preference_apply

logger = logging.getLogger(__name__)
router = APIRouter()


async def _반영(user_id: str) -> None:
    try:
        await preference_apply.apply_feedback(user_id)
    except Exception:
        # 배경 작업이라 올려도 받을 곳이 없다. 남은 일은 다음 호출이 이어서 한다.
        logger.exception("피드백 반영 실패 user=%s", user_id)


@router.post("/feedback/apply", status_code=status.HTTP_202_ACCEPTED)
async def feedback_apply(req: FeedbackApplyRequest, tasks: BackgroundTasks) -> Accepted:
    tasks.add_task(_반영, req.user_id)
    return Accepted()
