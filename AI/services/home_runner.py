"""홈 맞춤 추천 카드를 만든다. BE 의 일일 배치가 사용자, 종류마다 부른다.

    1. 사용자 프로필과 선호 가중치를 읽는다
    2. 질의 없이 홈 경로(HOME_ENV, HOME_ROUTINE)를 돌린다. 진행률은 남기지 않는다
    3. 성공하면 home_recommendations 를 덮어쓴다

실패하면 쓰지 않는다. 어제 카드가 그대로 남고, BE 배치가 오래된 것부터 다음 날 다시 부른다.
같은 (사용자, 종류)가 겹쳐 들어오면 차례로 돈다. 늦게 끝난 실행이 먼저 시작한 실행의
결과를 덮어쓰는 일은 있어도, 두 실행이 섞인 결과가 남지는 않는다.

꼭 필요한 단계가 아직 없는지는 runnable 로 먼저 본다. 라우터가 이것으로 stub 응답을 정한다.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from contracts.internal_api import HomeKind
from contracts.query_spec import QuerySpec, RequestType, Target

logger = logging.getLogger(__name__)

SCENARIO: dict[HomeKind, str] = {
    HomeKind.ENV: "HOME_ENV",
    HomeKind.ROUTINE: "HOME_ROUTINE",
}

_잠금: defaultdict[tuple[str, HomeKind], asyncio.Lock] = defaultdict(asyncio.Lock)


def missing_nodes(kind: HomeKind) -> list[str]:
    """이 종류의 홈 경로에 꼭 필요한데 아직 없는 단계."""
    from graph.builder import _load
    from graph.nodes.compose import REQUIRED_NODES

    return [이름 for 이름 in REQUIRED_NODES.get(SCENARIO[kind], ()) if _load(이름) is None]


def initial_state(user_id: str, kind: HomeKind, context: dict) -> dict:
    spec = QuerySpec(
        request_type=RequestType.SEARCH, target=Target.SELF, use_env=(kind == HomeKind.ENV),
    )
    return {
        "job_id": f"home:{user_id}:{kind.value}",
        "user_id": user_id,
        "scenario": SCENARIO[kind],
        "raw_query": "",
        "query_spec": spec.model_dump(mode="json"),
        "basis": Target.SELF.value,
        **context,
    }


async def run(user_id: str, kind: HomeKind) -> None:
    """홈 카드를 만들어 저장한다. 실패해도 예외를 올리지 않는다(배경 작업이다)."""
    from graph.builder import run_scenario
    from services import home_store, user_context

    async with _잠금[(user_id, kind)]:
        try:
            문맥 = await user_context.load(user_id, Target.SELF.value, None)
            상태 = await run_scenario(SCENARIO[kind], initial_state(user_id, kind, 문맥))
            await home_store.save(user_id, kind, 상태["result"])
        except Exception:
            logger.exception("홈 카드 생성 실패 user=%s kind=%s. 이전 카드를 그대로 둔다.",
                             user_id, kind.value)
