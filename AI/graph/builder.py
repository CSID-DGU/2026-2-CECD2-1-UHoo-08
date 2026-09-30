"""레지스트리를 읽어 실행 가능한 그래프를 만든다.

노드가 신경 쓰지 않아도 되는 일을 여기서 한다.

    진행률   각 단계 앞에서 "지금 무엇을 하는 중"을 기록한다
    trace    지나간 단계를 남긴다. 실패했을 때 어디까지 갔는지 보려면 필요하다
    실패     예외를 잡아 job 을 실패로 남기고 다시 올린다

노드마다 이걸 직접 하면 다섯 사람이 다섯 가지로 만든다.

아직 없는 노드는 pass-through 로 채운다. 경로가 항상 끝까지 돌아야 각자
자기 노드만 채워 넣으면서 진행 상황을 볼 수 있다.

DB 에는 직접 쓰지 않는다. 진행률·실패 기록은 콜백으로 받아, 빌더 자체는
API 키 없이도 테스트된다.
"""
from __future__ import annotations

import importlib
import logging
from typing import Awaitable, Callable

from langgraph.graph import END, START, StateGraph

from graph.registry import NODE_LABELS, SEARCH_ENTRY, full_path
from graph.state import GraphState

logger = logging.getLogger(__name__)

Node = Callable[[GraphState], Awaitable[dict]]
# (화면에 보일 문구, 0~100)
ProgressHook = Callable[[str, int], Awaitable[None]]
FailHook = Callable[[Exception], Awaitable[None]]


async def _pass_through(state: GraphState) -> dict:
    """아직 없는 노드. 상태를 그대로 흘려보낸다."""
    return {}


def _load(name: str) -> Node | None:
    """graph/nodes/<name>.py 의 같은 이름 함수를 가져온다. 없으면 None."""
    경로 = f"graph.nodes.{name}"
    try:
        module = importlib.import_module(경로)
    except ModuleNotFoundError as e:
        # 노드 파일이 없는 것과, 노드가 import 하는 것이 없는 것은 다르다.
        # 뒤엣것까지 stub 으로 넘기면 의존성 누락이 "아직 안 만든 노드"로
        # 위장되고, 경로는 조용히 아무 일도 하지 않는다.
        if e.name != 경로:
            raise
        return None

    fn = getattr(module, name, None)
    if fn is None:
        raise AttributeError(f"{경로} 에 async def {name}(state) 가 없다")
    return fn


def _wrap(
    name: str, fn: Node, 순번: int, 전체: int,
    on_progress: ProgressHook | None, 구간: tuple[int, int] = (0, 100),
) -> Node:
    문구 = NODE_LABELS.get(name, name)
    stub = fn is _pass_through

    async def 실행(state: GraphState) -> dict:
        if on_progress is not None:
            # 단계를 시작할 때 알린다. 끝나고 알리면 화면이 한 단계 늦는다.
            시작, 끝 = 구간
            await on_progress(문구, 시작 + round(순번 / 전체 * (끝 - 시작)))
        바뀐 = await fn(state)
        자취 = list(state.get("trace", []))
        자취.append(f"{name}(stub)" if stub else name)
        return {**(바뀐 or {}), "trace": 자취}

    return 실행


def build(
    scenario: str,
    *,
    use_env: bool = False,
    include_entry: bool = True,
    on_progress: ProgressHook | None = None,
    progress_from: int = 0,
):
    """시나리오 하나를 실행할 수 있는 그래프로 만든다.

    include_entry 가 False 면 Normalize·Router 를 뺀다. 이미 QuerySpec 을
    손에 들고 특정 경로만 돌려 보는 경우다.

    progress_from 은 진행률의 시작점이다. 관문을 먼저 돌린 뒤 경로를 도는
    경우, 0 부터 다시 세면 화면의 막대가 뒤로 돌아간다.
    """
    단계들 = full_path(scenario, use_env=use_env)
    if not include_entry:
        단계들 = tuple(s for s in 단계들 if s not in SEARCH_ENTRY)

    중복 = [s for s in 단계들 if 단계들.count(s) > 1]
    if 중복:
        # langgraph 는 같은 이름의 노드를 두 번 받지 못한다. 여기서 막지 않으면
        # 레지스트리를 고친 사람이 알아보기 어려운 오류를 보게 된다.
        raise ValueError(f"{scenario}: 같은 단계가 두 번 들어 있다 {sorted(set(중복))}")

    그래프 = StateGraph(GraphState)
    이전 = START
    전체 = len(단계들)
    for 순번, 이름 in enumerate(단계들):
        구현 = _load(이름)
        if 구현 is None:
            logger.info("노드 %s 는 아직 없다. 그대로 흘려보낸다.", 이름)
            구현 = _pass_through
        그래프.add_node(이름, _wrap(이름, 구현, 순번, 전체, on_progress, (progress_from, 100)))
        그래프.add_edge(이전, 이름)
        이전 = 이름
    그래프.add_edge(이전, END)
    return 그래프.compile()


async def run_scenario(
    scenario: str,
    initial: dict | None = None,
    *,
    include_entry: bool = False,
    on_progress: ProgressHook | None = None,
    on_fail: FailHook | None = None,
    progress_from: int = 0,
) -> GraphState:
    """경로 하나를 끝까지 돌린다.

    기본값은 Normalize·Router 를 건너뛴다. QuerySpec 을 직접 넣어 원하는
    경로만 확인하는 것이 이 함수의 주된 쓰임이고, 그래야 라우터가 완성되기
    전에도 각 파트가 자기 경로를 통합 테스트할 수 있다.
    """
    상태: dict = dict(initial or {})
    상태.setdefault("scenario", scenario)
    상태.setdefault("trace", [])

    use_env = bool((상태.get("query_spec") or {}).get("use_env"))
    그래프 = build(
        scenario,
        use_env=use_env,
        include_entry=include_entry,
        on_progress=on_progress,
        progress_from=progress_from,
    )

    try:
        결과 = await 그래프.ainvoke(상태)
    except Exception as e:
        # 삼키지 않는다. 부른 쪽이 job 을 실패로 남기고, 원인은 그대로 올린다.
        logger.exception("%s 실행 실패", scenario)
        if on_fail is not None:
            await on_fail(e)
        raise

    if on_progress is not None:
        await on_progress("완료", 100)
    return 결과


# 관문이 차지하는 진행률. 질의 해석은 전체에서 짧은 부분이라 앞쪽 10%만 쓴다.
관문_구간 = 10


async def run_query(
    initial: dict | None = None,
    *,
    on_progress: ProgressHook | None = None,
    on_fail: FailHook | None = None,
) -> GraphState:
    """질의를 해석하고, 그 결과가 가리키는 경로를 돈다.

    관문(Normalize·Router)은 그래프 안에 넣을 수 없다. 빌더는 시나리오를
    알아야 경로를 조립하는데, 그 시나리오를 정하는 것이 라우터이기 때문이다.
    그래서 관문을 먼저 돌리고, 나온 시나리오로 경로를 조립한다.

    되물어야 하는 질의면 경로를 돌지 않고 돌아온다. 부른 쪽이 job 을
    멈춘 상태로 남기고 사용자의 답을 기다린다.
    """
    상태: dict = dict(initial or {})
    상태.setdefault("trace", [])

    try:
        for 순번, 이름 in enumerate(SEARCH_ENTRY):
            구현 = _load(이름)
            if 구현 is None:
                logger.info("관문 %s 는 아직 없다. 그대로 흘려보낸다.", 이름)
                구현 = _pass_through
            단계 = _wrap(이름, 구현, 순번, len(SEARCH_ENTRY), on_progress, (0, 관문_구간))
            상태.update(await 단계(상태))
    except Exception as e:
        logger.exception("관문 실행 실패")
        if on_fail is not None:
            await on_fail(e)
        raise

    if 상태.get("clarify_question"):
        return 상태

    시나리오 = 상태.get("scenario") or 기본_시나리오()
    return await run_scenario(
        시나리오,
        상태,
        on_progress=on_progress,
        on_fail=on_fail,
        progress_from=관문_구간,
    )


def 기본_시나리오() -> str:
    """라우터가 아직 없을 때 갈 곳. 조건 탐색은 빈손으로도 돌아간다."""
    from contracts.query_spec import RequestType
    from graph.registry import ROUTE

    return ROUTE[RequestType.SEARCH]
