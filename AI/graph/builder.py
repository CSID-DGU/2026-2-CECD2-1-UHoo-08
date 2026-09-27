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


def _wrap(name: str, fn: Node, 순번: int, 전체: int, on_progress: ProgressHook | None) -> Node:
    문구 = NODE_LABELS.get(name, name)
    stub = fn is _pass_through

    async def 실행(state: GraphState) -> dict:
        if on_progress is not None:
            # 단계를 시작할 때 알린다. 끝나고 알리면 화면이 한 단계 늦는다.
            await on_progress(문구, round(순번 / 전체 * 100))
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
):
    """시나리오 하나를 실행할 수 있는 그래프로 만든다.

    include_entry 가 False 면 Normalize·Router 를 뺀다. 이미 QuerySpec 을
    손에 들고 특정 경로만 돌려 보는 경우다.
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
        그래프.add_node(이름, _wrap(이름, 구현, 순번, 전체, on_progress))
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
