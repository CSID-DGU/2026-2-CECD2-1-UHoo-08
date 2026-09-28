"""추천 실행과 되묻기 답변.

둘 다 비동기다. 결과는 응답이 아니라 recommendation_jobs 로 간다.
BE 는 job 을 조회해 진행 상태를 본다.

되묻기는 이렇게 돈다.

    run/v2  →  관문  →  물어볼 것이 있다  →  job 을 NEEDS_CLARIFICATION 으로
                                            두고 멈춘 시점의 상태를 남긴다
    clarify →  남긴 상태를 꺼내 답을 얹고 다시 관문부터 돈다

DB 를 쓰는 것은 실행을 맡는 함수 안에서만 import 한다. 모듈 최상단에서
가져오면 config 를 타고 API 키를 요구해, 키 없이는 이 라우터 자체가 뜨지
않는다. 그러면 경로 테스트도 못 돈다.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, status

from contracts.internal_api import Accepted, AgentClarifyRequest, AgentRunV2Request, JobStatus
from contracts.query_spec import Target
from contracts.result import Clarify, QuerySummary, RecommendationResult
from graph import builder

logger = logging.getLogger(__name__)
router = APIRouter()

# 멈출 때 남겨 두는 값. 답을 받아 이어 돌리는 데 필요한 것만 담는다.
# 경로를 돌기 전에 멈추므로 후보는 아직 없다.
_남길_키 = (
    "job_id", "user_id", "raw_query", "basis", "target_profile",
    "parent_job_id", "query_spec", "scenario",
    "clarify_question", "clarify_count",
)


def _결과를_만들_수_있나() -> bool:
    """결과를 조립하는 단계가 실제로 있는지 본다.

    compose 가 아직 없으면 job 은 완료되지만 결과가 비어 있다. 호출한 쪽이
    그것을 '추천 없음' 으로 읽지 않도록 응답에 표시한다. compose 가 들어오면
    따로 고치지 않아도 표시가 사라진다.
    """
    return builder._load("compose") is not None


def _되묻는_결과(상태: dict, 질문: str) -> dict:
    """화면이 그대로 그릴 수 있는 모양으로 질문을 담는다.

    별도 필드로 내보내지 않고 결과 스키마의 clarify 자리를 쓴다. FE 가
    결과를 읽는 경로 하나만 알면 되도록 하려는 것이다.
    """
    spec = 상태.get("query_spec") or {}
    return RecommendationResult(
        job_id=상태["job_id"],
        scenario=상태.get("scenario") or builder.기본_시나리오(),
        query=QuerySummary(
            raw=상태.get("raw_query") or "",
            category=spec.get("category"),
            conditions=spec.get("conditions") or [],
            target=상태.get("basis") or Target.SELF,
        ),
        clarify=Clarify(question=질문),
    ).model_dump(mode="json", by_alias=True)


async def _돌리기(상태: dict) -> None:
    """관문부터 끝까지 돌리고 결과를 job 에 적는다."""
    from services import job_store, job_updater

    job_id = 상태["job_id"]

    async def 진행(문구: str, 비율: int) -> None:
        await job_updater.update(
            job_id, step=문구, progress=비율, status=JobStatus.IN_PROGRESS.value
        )

    async def 실패(e: Exception) -> None:
        await job_updater.update(
            job_id, status=JobStatus.FAILED.value, error_msg=str(e)
        )

    try:
        결과 = await builder.run_query(상태, on_progress=진행, on_fail=실패)
    except Exception:
        # 실패 기록은 on_fail 이 이미 남겼다. 배경 작업이라 올려도 받을 곳이 없다.
        return

    질문 = 결과.get("clarify_question")
    if 질문:
        # 되묻는 중은 실패가 아니다. job 을 멈춘 채로 두고 답을 기다린다.
        # 답이 오면 남긴 상태를 꺼내 이어서 돈다.
        await job_store.save_snapshot(
            job_id, {키: 결과.get(키) for 키 in _남길_키 if 결과.get(키) is not None}
        )
        await job_updater.update(
            job_id,
            status=JobStatus.NEEDS_CLARIFICATION.value,
            step="되묻는 중",
            result=_되묻는_결과(결과, 질문),
        )
        return

    await job_updater.update(
        job_id,
        status=JobStatus.COMPLETED.value,
        progress=100,
        result=결과.get("result") or {},
    )


async def _실행(req: AgentRunV2Request) -> None:
    await _돌리기({
        "job_id": req.job_id,
        "user_id": req.user_id,
        "raw_query": req.raw_query,
        "basis": req.basis.value,
        "target_profile": req.target_profile,
        "parent_job_id": req.parent_job_id,
    })


async def _이어_돌리기(req: AgentClarifyRequest) -> None:
    from services import job_store

    job = await job_store.load_job(req.job_id)
    if job is None:
        return

    # 멈춰 있는 job 이 아니면 아무것도 하지 않는다. 이미 끝난 job 을 다시
    # 돌리면 사용자가 보고 있던 결과가 덮인다.
    if job.get("status") != JobStatus.NEEDS_CLARIFICATION.value:
        logger.warning(
            "clarify: job %s 는 %s 상태다. 답을 무시한다.", req.job_id, job.get("status")
        )
        return

    상태 = dict(job.get("state_snapshot") or {})
    상태["job_id"] = req.job_id
    상태["clarify_answer"] = req.answer
    # 몇 번 물었는지는 라우터가 본다. 올리지 않으면 같은 것을 계속 묻는다.
    상태["clarify_count"] = (상태.get("clarify_count") or 0) + 1
    # 이전 질문은 답과 함께 Normalize 가 읽는다. 다시 물을지는 라우터가 정한다.
    상태.pop("scenario", None)

    await _돌리기(상태)


@router.post("/agent/run/v2", status_code=status.HTTP_202_ACCEPTED)
async def run_v2(req: AgentRunV2Request, tasks: BackgroundTasks) -> Accepted:
    tasks.add_task(_실행, req)
    return Accepted(job_id=req.job_id, stub=not _결과를_만들_수_있나())


@router.post("/agent/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify(req: AgentClarifyRequest, tasks: BackgroundTasks) -> Accepted:
    tasks.add_task(_이어_돌리기, req)
    return Accepted(job_id=req.job_id, stub=not _결과를_만들_수_있나())
