"""추천 실행과 되묻기 답변.

둘 다 비동기다. 결과는 응답이 아니라 recommendation_jobs 로 간다.
BE 는 job 을 조회해 진행 상태를 본다.
"""
import logging

from fastapi import APIRouter, status

from contracts.internal_api import Accepted, AgentClarifyRequest, AgentRunV2Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agent/run/v2", status_code=status.HTTP_202_ACCEPTED)
async def run_v2(req: AgentRunV2Request) -> Accepted:
    # TODO: 빌더가 들어오면 run_scenario 로 이어붙인다.
    logger.warning("stub: /agent/run/v2 job=%s query=%r", req.job_id, req.raw_query)
    return Accepted(job_id=req.job_id, stub=True)


@router.post("/agent/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify(req: AgentClarifyRequest) -> Accepted:
    # TODO: NEEDS_CLARIFICATION 으로 멈춘 job 의 스냅샷을 꺼내 재개한다.
    logger.warning("stub: /agent/clarify job=%s", req.job_id)
    return Accepted(job_id=req.job_id, stub=True)
