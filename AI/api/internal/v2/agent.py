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

# 끝난 job 에 남기는 값. 그대로 옮기는 것과 줄여서 옮기는 것이 있다.
# intent_vector 와 product_meta 는 넣지 않는다. 크기만 크고 다시 만들 수 있다.
_완료_그대로_키 = (
    "scenario", "query_spec", "user_id", "basis", "target_profile",
    "parent_job_id", "raw_query", "bundle_slots", "trace",
)
# 조건 수정이 부모의 후보를 다시 정렬할 때 쓰는 개수. 결과 10개를 고르기에 넉넉하다.
스냅샷_후보_상한 = 60
_후보_키 = ("product_id", "source", "similarity", "slot_key")


def _결과를_만들_수_있나() -> bool:
    """결과를 조립하는 단계가 실제로 있는지 본다.

    compose 가 아직 없으면 돌려도 빈 결과로 완료된다. 그러면 상태 조회는
    완료라 하고 결과 조회는 상품 없는 성공이 되어, 호출한 쪽은 '추천 없음'
    으로 읽는다. 그래서 이때는 실행을 걸지 않고 응답에 표시만 한다. job 은
    PENDING 으로 남고, 멈춘 job 정리 배치가 기한이 지나면 FAILED 로 바꾼다.
    compose 가 들어오면 따로 고치지 않아도 실행이 걸리고 표시가 사라진다.
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
        clarify=Clarify(
            question=질문,
            missing_fields=상태.get("clarify_missing_fields") or [],
        ),
    ).model_dump(mode="json", by_alias=True)


def _완료_스냅샷(상태: dict) -> dict:
    """끝난 job 의 state_snapshot.

    BE 는 대체 후보를 뺀 수와 세트 칸을 여기서 읽고, 조건 수정은 부모의
    후보와 질의를 여기서 꺼낸다. JSON 으로 옮길 수 있는 값만 담는다.
    """
    스냅샷 = {키: 상태[키] for 키 in _완료_그대로_키 if 상태.get(키) is not None}
    스냅샷["candidates"] = [
        {키: 후보[키] for 키 in _후보_키 if 후보.get(키) is not None}
        for 후보 in (상태.get("candidates") or [])[:스냅샷_후보_상한]
    ]
    스냅샷["scored"] = [
        {"product_id": 항목["product_id"], "total": 항목["total"]}
        for 항목 in 상태.get("scored") or []
    ]
    스냅샷["alternatives_dropped_count"] = 상태.get("alternatives_dropped_count") or 0
    return 스냅샷


async def _돌리기(상태: dict) -> None:
    """사용자 맥락을 채우고, 관문부터 끝까지 돌리고, 결과를 job 에 적는다."""
    from services import job_store, job_updater, user_context

    job_id = 상태["job_id"]

    # 프로필은 스냅샷에 남기지 않고 돌릴 때마다 읽는다. 되묻기 답변으로
    # 이어 돌릴 때도 남긴 추천 기준으로 다시 읽는다.
    try:
        상태.update(await user_context.load(
            상태["user_id"], 상태.get("basis") or Target.SELF.value, 상태.get("target_profile"),
        ))
    except Exception as e:
        logger.exception("사용자 맥락을 읽지 못했다 job=%s", job_id)
        await job_updater.update(job_id, status=JobStatus.FAILED.value, error_msg=str(e))
        return

    async def 진행(문구: str, 비율: int, 단계들: list[dict]) -> None:
        await job_updater.update(
            job_id, step=문구, progress=비율, status=JobStatus.IN_PROGRESS.value, steps=단계들
        )

    async def 실패(e: Exception) -> None:
        await job_updater.update(
            job_id, status=JobStatus.FAILED.value, error_msg=str(e)
        )

    async def 경로(정해진: dict) -> None:
        # 진행 중에도 BE 상태 조회에 시나리오가 보이게 경로가 정해지자마자 적는다.
        await job_updater.update(
            job_id, scenario=정해진.get("scenario"), query_spec=정해진.get("query_spec")
        )

    try:
        결과 = await builder.run_query(
            상태, on_progress=진행, on_fail=실패, on_route=경로
        )
    except Exception:
        # 실패 기록은 on_fail 이 이미 남겼다. 배경 작업이라 올려도 받을 곳이 없다.
        return

    async def 스냅샷_남기기(스냅샷: dict) -> bool:
        # 스냅샷을 못 남기면 이어 돌리기도, 조건 수정도 할 수 없다.
        # 진행 중으로 남겨 두지 않고 바로 실패로 적는다.
        try:
            await job_store.save_snapshot(job_id, 스냅샷)
        except Exception as e:
            logger.exception("스냅샷을 남기지 못했다 job=%s", job_id)
            await 실패(e)
            return False
        return True

    질문 = 결과.get("clarify_question")
    if 질문:
        # 되묻는 중은 실패가 아니다. job 을 멈춘 채로 두고 답을 기다린다.
        # 답이 오면 남긴 상태를 꺼내 이어서 돈다.
        if not await 스냅샷_남기기(
            {키: 결과.get(키) for 키 in _남길_키 if 결과.get(키) is not None}
        ):
            return
        await job_updater.update(
            job_id,
            status=JobStatus.NEEDS_CLARIFICATION.value,
            step="되묻는 중",
            result=_되묻는_결과(결과, 질문),
        )
        return

    # 스냅샷을 먼저 남긴다. 완료를 먼저 적으면 BE 가 스냅샷이 비어 있는
    # 완료 job 을 읽을 수 있다.
    if not await 스냅샷_남기기(_완료_스냅샷(결과)):
        return
    # 조건 수정은 경로 중에 질의가 부모 조건과 합쳐지므로 완료 때 한 번 더 적는다.
    await job_updater.update(
        job_id,
        status=JobStatus.COMPLETED.value,
        progress=100,
        result=결과.get("result") or {},
        scenario=결과.get("scenario"),
        query_spec=결과.get("query_spec"),
    )


async def _실행(req: AgentRunV2Request) -> None:
    await _돌리기({
        "job_id": req.job_id,
        "user_id": req.user_id,
        "raw_query": req.raw_query or "",
        "base_product_id": req.base_product_id,
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
    if not _결과를_만들_수_있나():
        logger.warning("stub: /agent/run/v2 job=%s 는 실행하지 않는다", req.job_id)
        return Accepted(job_id=req.job_id, stub=True)
    tasks.add_task(_실행, req)
    return Accepted(job_id=req.job_id)


@router.post("/agent/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify(req: AgentClarifyRequest, tasks: BackgroundTasks) -> Accepted:
    if not _결과를_만들_수_있나():
        logger.warning("stub: /agent/clarify job=%s 는 실행하지 않는다", req.job_id)
        return Accepted(job_id=req.job_id, stub=True)
    tasks.add_task(_이어_돌리기, req)
    return Accepted(job_id=req.job_id)
