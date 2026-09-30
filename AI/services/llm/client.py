"""OpenAI 호환 엔드포인트를 쓰는 채팅 클라이언트.

DashScope 도 Gemini 도 OpenAI 호환 주소를 주므로, 모델·주소·키만 바꾸면
같은 코드로 다른 제공자를 쓸 수 있다. 어떤 값을 쓸지는 역할이 정한다.

    from services.llm import LLMRole, get_llm

    llm = get_llm(LLMRole.WEIGHT)
    weights = await llm.chat_json(system="...", user="...")

동기 SDK 를 to_thread 로 감싸 async 로 내보낸다. FastAPI 안에서 그대로
부르면 이벤트 루프가 멈춘다.
"""
from __future__ import annotations

import asyncio
import json
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional

from openai import OpenAI

from config import settings


class LLMRole(str, Enum):
    """모델을 따로 고를 수 있는 자리.

    쓰임이 다르면 필요한 능력도 다르다. 질의를 규격화된 JSON 으로 옮기는 일은
    형식을 정확히 지켜야 하고, 가중치를 보정하는 일은 숫자 감각이 필요하고,
    설명 문장을 쓰는 일은 문장력이 필요하다. 한 모델로 묶어 두면 어디를
    올려야 좋아지는지 알 수 없다.
    """

    NORMALIZE = "normalize"  # 질의 → QuerySpec
    WEIGHT = "weight"        # 점수 가중치 보정
    COMPOSE = "compose"      # 추천 이유 문장
    VLM = "vlm"              # 사진 인식


# 환경 변수를 비워 뒀을 때 쓰는 값. 지금 쓰고 있는 모델 그대로다.
_기본_모델 = {
    LLMRole.NORMALIZE: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.WEIGHT: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.COMPOSE: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.VLM: lambda: settings.QWEN_VL_MODEL,
}

_기본_주소 = {
    LLMRole.VLM: lambda: settings.QWEN_VL_BASE_URL,
}


def _설정(role: LLMRole) -> tuple[str, str, str]:
    """역할 하나가 쓸 모델·주소·키. 비어 있으면 기본값으로 떨어진다."""
    이름 = role.name
    모델 = getattr(settings, f"LLM_{이름}_MODEL", "") or _기본_모델[role]()
    주소 = (
        getattr(settings, f"LLM_{이름}_BASE_URL", "")
        or _기본_주소.get(role, lambda: settings.QWEN_TEXT_BASE_URL)()
    )
    키 = getattr(settings, f"LLM_{이름}_API_KEY", "") or settings.DASHSCOPE_API_KEY
    return 모델, 주소, 키


class LLMClient:
    """채팅 호출 래퍼. 동기 SDK를 to_thread로 감싸 async 노출."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def chat(
        self,
        system: str,
        user: str,
        response_json: bool = False,
        temperature: float = 0.0,
    ) -> str:
        """
        chat completion 호출.

        response_json=True면 response_format을 json_object로 강제하고
        파싱 가능한 JSON 문자열만 반환.
        """
        def _do_call() -> str:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
            if response_json:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""

        return await asyncio.to_thread(_do_call)

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """JSON 응답 호출 + 파싱. 파싱 실패 시 None."""
        raw = await self.chat(system, user, response_json=True, temperature=temperature)
        if not raw:
            return None
        # 코드블록 펜스 방어
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


@lru_cache(maxsize=len(LLMRole))
def get_llm(role: LLMRole) -> LLMClient:
    """역할 하나에 클라이언트 하나. 같은 역할은 매번 같은 것을 돌려준다."""
    모델, 주소, 키 = _설정(role)
    return LLMClient(model=모델, base_url=주소, api_key=키)