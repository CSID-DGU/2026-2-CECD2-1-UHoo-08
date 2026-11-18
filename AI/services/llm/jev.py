"""의사결정 모델 Jev(TypeSafe) 호출.

Jev 는 글을 쓰지 못한다. 내용(state)과 질문을 주면 미리 정한 보기 중 하나를
확률과 함께 고르거나(choice), 예일 확률을 0~1 로 낸다(noul).

    from services.llm.jev import ask, choice, noul

    답 = await ask("라운드랩 독도 토너 어때?", {
        "종류": choice("어떤 요청인가?", {"SEARCH": "...", "EVALUATE": "..."}),
        "막연함": noul("되물어야 하는가?"),
    })
    답["종류"]["choice"], 답["종류"]["probabilities"], 답["막연함"]["noul"]

채팅 모델이 아니라서 get_llm 의 역할에는 넣지 않고 따로 둔다. SDK 를 쓰지 않고
HTTP 로 직접 불러 의존성을 늘리지 않는다. 지금은 시나리오 결정 실험(eval)에서만 쓴다.
호출 기록은 LLM 과 같은 곳에 남겨 비용과 시간을 함께 잰다.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from config import settings
from services.llm.usage import LLMCall, record

# 요청 하나를 기다리는 시간(초). Jev 는 보통 0.2초 안에 답한다
_기다림 = 10.0
# 잠깐의 오류(요청이 몰림, 서버 오류)는 한 번만 다시 보낸다
_다시_보낼_상태 = frozenset({429, 500, 502, 503, 504})

_클라이언트: Optional[httpx.AsyncClient] = None


def choice(instructions: str, criteria: dict[str, Any]) -> dict:
    """보기 중 하나를 고르는 질문. criteria 는 보기 이름과 그 설명이다."""
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul(instructions: str) -> dict:
    """예/아니오 질문. 답은 예일 확률이다."""
    return {"type": "noul", "instructions": instructions}


def _client() -> httpx.AsyncClient:
    """연결을 다시 쓴다. 호출마다 새로 맺으면 그 시간이 걸린 시간에 섞인다."""
    global _클라이언트
    if _클라이언트 is None or _클라이언트.is_closed:
        if not settings.TYPESAFE_API_KEY:
            raise RuntimeError("TYPESAFE_API_KEY 가 비어 있다. AI/.env 에 넣는다")
        _클라이언트 = httpx.AsyncClient(
            base_url=settings.TYPESAFE_BASE_URL,
            headers={"Authorization": f"Bearer {settings.TYPESAFE_API_KEY}"},
            timeout=_기다림,
        )
    return _클라이언트


async def ask(state: Any, questions: dict[str, dict]) -> dict[str, dict]:
    """Jev 에 묻고 질문 이름별 답을 돌려준다. 실패하면 예외를 올린다."""
    본문 = {"model": settings.TYPESAFE_MODEL, "state": state, "questions": questions}
    시작 = time.perf_counter()
    try:
        응답 = await _client().post("/v1/systemone", json=본문)
        if 응답.status_code in _다시_보낼_상태:
            await asyncio.sleep(0.5)
            응답 = await _client().post("/v1/systemone", json=본문)
        응답.raise_for_status()
        받은 = 응답.json()
    except Exception:
        record(LLMCall(role="jev", model=settings.TYPESAFE_MODEL, input_tokens=0,
                       output_tokens=0, seconds=time.perf_counter() - 시작, ok=False))
        raise

    사용 = 받은.get("usage") or {}
    record(LLMCall(
        role="jev",
        # 별칭으로 불렀어도 실제로 답한 버전을 남긴다
        model=받은.get("model") or settings.TYPESAFE_MODEL,
        input_tokens=int(사용.get("input_tokens") or 0),
        output_tokens=int(사용.get("output_tokens") or 0),
        seconds=time.perf_counter() - 시작,
    ))
    return 받은["answers"]
