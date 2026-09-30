"""추천 job 의 상태 스냅샷을 남기고 다시 꺼낸다.

되묻는 동안 job 은 멈춰 있다. 답이 왔을 때 이어 돌리려면 멈춘 시점의 값이
남아 있어야 한다. 원래 질의가 무엇이었는지, 무엇을 물었는지, 몇 번 물었는지를
모르면 답만 가지고는 아무것도 할 수 없다.

조건 수정(S7)도 같은 자리를 쓴다. 직전 job 의 후보와 조건을 꺼내 쓰면 같은
검색을 처음부터 다시 하지 않아도 된다.

무엇을 담을지는 부르는 쪽이 정한다. 되묻기는 경로를 돌기 전이라 담을 것이
적고, 조건 수정은 후보까지 담는다. 여기서 한 벌로 정해 두면 둘 중 하나는
필요 없는 것을 지고 다니거나 필요한 것을 잃는다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_TABLE = "recommendation_jobs"


async def save_snapshot(job_id: str, snapshot: dict[str, Any]) -> None:
    """멈춘 시점의 값을 남긴다.

    JSON 으로 옮길 수 있는 값만 담는다. datetime 같은 것을 넣으면 저장할 때
    터지는데, 그 시점은 이미 사용자가 답을 보낸 뒤라 되돌릴 수 없다.
    """
    import asyncio

    from db.supabase_client import get_supabase

    def _쓰기() -> None:
        get_supabase().table(_TABLE).update(
            {"state_snapshot": snapshot}
        ).eq("id", job_id).execute()

    await asyncio.to_thread(_쓰기)


async def load_job(job_id: str) -> dict[str, Any] | None:
    """job 하나를 읽는다. 없으면 None."""
    import asyncio

    from db.supabase_client import get_supabase

    def _읽기() -> list[dict]:
        return (
            get_supabase().table(_TABLE)
            .select("id, user_id, status, state_snapshot")
            .eq("id", job_id)
            .limit(1)
            .execute()
        ).data or []

    행 = await asyncio.to_thread(_읽기)
    if not 행:
        logger.warning("job %s 를 찾지 못했다", job_id)
        return None
    return 행[0]
