"""
recommendation_jobs 테이블의 step / progress / status를 업데이트.

각 추천 에이전트가 완료될 때마다 호출되어 Spring 폴링 응답이 진행 상태를
반영하게 한다.

supabase-py는 동기 API라서 asyncio.to_thread로 감싸 이벤트 루프를 차단하지 않게 한다.
(supabase-py는 “기다리는 동안 멈추는 코드(sync/blocking)”라서,
async 서버(FastAPI) 안에서 그대로 쓰면 전체 흐름이 막힐 수 있다.
그래서 별도 thread로 보내서 기다리게 한다.)

사용 예:
    from services.job_updater import update

    await update(job_id, step="후보 탐색", progress=25, status="IN_PROGRESS")
    await update(job_id, step="루틴 생성", progress=100, status="COMPLETED", result={...})
    await update(job_id, status="FAILED", error_msg="...")
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from db.supabase_client import get_supabase


async def update(
    job_id: str,
    step: Optional[str] = None,
    progress: Optional[int] = None,
    status: Optional[str] = None,
    error_msg: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    """
    recommendation_jobs row를 부분 갱신.

    None인 파라미터는 갱신하지 않음 (부분 업데이트 안전).
    updated_at은 항상 현재 시각으로 갱신.
    """
    payload: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
    if step is not None:
        payload["step"] = step
    if progress is not None:
        payload["progress"] = progress
    if status is not None:
        payload["status"] = status
    if error_msg is not None:
        payload["error_msg"] = error_msg
    if result is not None:
        payload["result"] = result

    def _do_update():
        sb = get_supabase()
        sb.table("recommendation_jobs").update(payload).eq("id", job_id).execute()

    await asyncio.to_thread(_do_update)