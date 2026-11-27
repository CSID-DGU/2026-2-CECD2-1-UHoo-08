"""LLM 호출 기록.

호출 한 번마다 어떤 모델을 불렀고, 토큰을 얼마나 썼고, 얼마나 걸렸는지를 남긴다.
비용과 속도를 어림이 아니라 기록으로 계산하기 위해서다.

기록은 로그로 한 줄 남기고, 모으는 중이라면 목록에도 담는다.

    from services.llm.usage import collect_calls

    with collect_calls() as 기록:
        await normalize(state)
    토큰 = sum(c.input_tokens + c.output_tokens for c in 기록)

모으는 범위는 contextvar 로 잡는다. 그 안에서 만든 asyncio 작업은 같은 목록을
물려받으므로, 같은 질문을 동시에 여러 번 보내도 한 목록에 모인다.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMCall:
    """호출 한 번의 기록."""

    role: str            # 역할 이름. 역할 없이 만든 클라이언트면 빈 문자열
    model: str
    input_tokens: int
    output_tokens: int
    seconds: float       # 요청을 보내고 응답을 받기까지 걸린 시간
    ok: bool = True      # 응답을 받지 못하고 끝났으면 False


_모으는_목록: ContextVar[Optional[list[LLMCall]]] = ContextVar("llm_calls", default=None)


@contextmanager
def collect_calls() -> Iterator[list[LLMCall]]:
    """이 범위 안에서 일어난 호출을 목록에 모은다."""
    목록: list[LLMCall] = []
    토큰 = _모으는_목록.set(목록)
    try:
        yield 목록
    finally:
        _모으는_목록.reset(토큰)


def token_counts(usage: Any) -> tuple[int, int]:
    """응답의 usage 에서 입력, 출력 토큰 수를 꺼낸다. 없으면 0 으로 본다.

    제공자에 따라 usage 를 주지 않거나 일부만 채우는 일이 있다. 기록 때문에
    호출이 실패하면 안 되므로 읽지 못한 값은 0 으로 둔다.
    """
    def _수(이름: str) -> int:
        값 = getattr(usage, 이름, None)
        return 값 if isinstance(값, int) else 0

    return _수("prompt_tokens"), _수("completion_tokens")


def record(call: LLMCall) -> None:
    """호출 하나를 로그에 남기고, 모으는 중이면 목록에도 담는다."""
    logger.info(
        "llm_call role=%s model=%s input_tokens=%d output_tokens=%d seconds=%.3f ok=%s",
        call.role, call.model, call.input_tokens, call.output_tokens, call.seconds, call.ok,
    )
    목록 = _모으는_목록.get()
    if 목록 is not None:
        목록.append(call)
