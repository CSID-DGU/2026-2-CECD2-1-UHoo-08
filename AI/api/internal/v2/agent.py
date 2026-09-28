"""추천 실행과 되묻기 답변.

둘 다 비동기다. 결과는 응답이 아니라 recommendation_jobs 로 간다.
BE 는 job 을 조회해 진행 상태를 본다.

DB 를 쓰는 것은 실행을 맡는 함수 안에서만 import 한다. 모듈 최상단에서
가져오면 config 를 타고 API 키를 요구해, 키 없이는 이 라우터 자체가 뜨지
않는다. 그러면 경로 테스트도 못 돈다.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, status

from contracts.internal_api import Accepted, AgentClarifyRequest, AgentRunV2Request, JobStatus
from contracts.result import Clarify, QuerySummary, RecommendationResult
from graph import builder

logger = logging.getLogger(__name__)
router = APIRouter()


def _결과를_만들_수_있나() -> bool:
    """결과를 조립하는 단계가 실제로 있는지 본다.

    compose 가 아직 없으면 job 은 완료되지만 결과가 비어 있다. 호출한 쪽이
    그것을 '추천 없음' 으로 읽지 않도록 응답에 표시한다. compose 가 들어오면
    따로 고치지 않아도 표시가 사라진다.
    """
    return builder._load("compose") is not None


async def _실행(req: AgentRunV2Request) -> None:
    from services import job_updater

    async def 진행(문구: str, 비율: int) -> None:
        await job_updater.update(
            req.job_id, step=문구, progress=비율, status=JobStatus.IN_PROGRESS.value
        )

    async def 실패(e: Exception) -> None:
        await job_updater.update(
            req.job_id, status=JobStatus.FAILED.value, error_msg=str(e)
        )

    try:
        결과 = await builder.run_query(
            {
                "job_id": req.job_id,
                "user_id": req.user_id,
                "raw_query": req.raw_query,
                "target_profile": req.target_profile,
                "parent_job_id": req.parent_job_id,
            },
            on_progress=진행,
            on_fail=실패,
        )
    except Exception:
        # 실패 기록은 on_fail 이 이미 남겼다. 배경 작업이라 올려도 받을 곳이 없다.
        return

    질문 = 결과.get("clarify_question")
    if 질문:
        # 되묻는 중은 실패가 아니다. job 을 멈춘 채로 두고 답을 기다린다.
        # 답이 오면 /agent/clarify 가 이어서 돌린다.
        await job_updater.update(
            req.job_id,
            status=JobStatus.NEEDS_CLARIFICATION.value,
            step="되묻는 중",
            result=_되묻는_결과(req, 결과, 질문),
        )
        return

    await job_updater.update(
        req.job_id,
        status=JobStatus.COMPLETED.value,
        progress=100,
        result=결과.get("result") or {},
    )


def _되묻는_결과(req: AgentRunV2Request, 상태: dict, 질문: str) -> dict:
    """화면이 그대로 그릴 수 있는 모양으로 질문을 담는다.

    별도 필드로 내보내지 않고 결과 스키마의 clarify 자리를 쓴다. FE 가
    결과를 읽는 경로 하나만 알면 되도록 하려는 것이다.
    """
    spec = 상태.get("query_spec") or {}
    return RecommendationResult(
        job_id=req.job_id,
        scenario=상태.get("scenario") or builder.기본_시나리오(),
        query=QuerySummary(
            raw=req.raw_query,
            category=spec.get("category"),
            conditions=spec.get("conditions") or [],
            target=req.basis,
        ),
        clarify=Clarify(question=질문),
    ).model_dump(mode="json", by_alias=True)


@router.post("/agent/run/v2", status_code=status.HTTP_202_ACCEPTED)
async def run_v2(req: AgentRunV2Request, tasks: BackgroundTasks) -> Accepted:
    tasks.add_task(_실행, req)
    return Accepted(job_id=req.job_id, stub=not _결과를_만들_수_있나())


@router.post("/agent/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify(req: AgentClarifyRequest) -> Accepted:
    # TODO: NEEDS_CLARIFICATION 으로 멈춘 job 의 스냅샷을 꺼내 재개한다.
    logger.warning("stub: /agent/clarify job=%s", req.job_id)
    return Accepted(job_id=req.job_id, stub=True)
