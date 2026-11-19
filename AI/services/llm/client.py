"""역할별 채팅 클라이언트.

DashScope 도 Gemini 도 OpenAI 호환 주소를 주므로, 모델, 주소, 키만 바꾸면
같은 코드로 다른 제공자를 쓸 수 있다. 어떤 값을 쓸지는 역할이 정한다.

둘은 다르게 부른다. 모델 이름이 claude- 로 시작하면 Anthropic SDK 를
쓰고(services.llm.claude), gemini- 로 시작하는데 주소를 따로 주지 않았으면
Vertex AI 로 부른다(services.llm.vertex). 부르는 쪽 코드는 같다.

    from services.llm import LLMRole, get_llm

    llm = get_llm(LLMRole.WEIGHT)
    weights = await llm.chat_json(system="...", user="...")

동기 SDK 를 to_thread 로 감싸 async 로 내보낸다. FastAPI 안에서 그대로
부르면 이벤트 루프가 멈춘다.

호출마다 모델, 토큰 수, 걸린 시간을 기록한다(services.llm.usage).
"""
from __future__ import annotations

import asyncio
import json
import time
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional

from openai import OpenAI

from config import settings
from services.llm.claude import DEFAULT_BASE_URL as CLAUDE_BASE_URL
from services.llm.claude import ClaudeChat, is_claude
from services.llm.usage import LLMCall, record, token_counts
from services.llm.vertex import VertexChat, is_gemini


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
    AD = "ad"                # 인스타 캡션 광고 판별 (1차 규칙이 못 정한 것)


# 환경 변수를 비워 뒀을 때 쓰는 값. 지금 쓰고 있는 모델 그대로다.
_기본_모델 = {
    LLMRole.NORMALIZE: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.WEIGHT: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.COMPOSE: lambda: settings.QWEN_TEXT_MODEL,
    LLMRole.VLM: lambda: settings.QWEN_VL_MODEL,
    LLMRole.AD: lambda: settings.QWEN_TEXT_MODEL,
}

_기본_주소 = {
    LLMRole.VLM: lambda: settings.QWEN_VL_BASE_URL,
}


def _설정(role: LLMRole) -> tuple[str, str, str]:
    """역할 하나가 쓸 모델, 주소, 키. 비어 있으면 기본값으로 떨어진다.

    주소와 키의 기본값은 모델을 보고 고른다. 모델만 Claude 로 바꿨는데
    Qwen 주소와 키로 부르는 일이 없게 한다.

    Gemini 는 주소를 비운 채로 돌려준다. 주소가 없는 Gemini 를 LLMClient 가
    Vertex AI 로 부른다. 구글 클라우드 프로젝트를 정해 두었을 때만 그렇게 한다.
    """
    이름 = role.name
    모델 = getattr(settings, f"LLM_{이름}_MODEL", "") or _기본_모델[role]()
    주소 = getattr(settings, f"LLM_{이름}_BASE_URL", "")
    키 = getattr(settings, f"LLM_{이름}_API_KEY", "")
    if is_claude(모델):
        return 모델, 주소 or CLAUDE_BASE_URL, 키 or settings.ANTHROPIC_API_KEY
    if is_gemini(모델) and not 주소 and settings.GOOGLE_CLOUD_PROJECT:
        return 모델, "", ""
    return (
        모델,
        주소 or _기본_주소.get(role, lambda: settings.QWEN_TEXT_BASE_URL)(),
        키 or settings.DASHSCOPE_API_KEY,
    )


# 생각 기능이 기본으로 켜져 있어, 끄는 값을 함께 보내야 하는 모델.
# 그대로 두면 짧은 변환 하나에 1분 넘게 걸리고 출력 토큰이 수십 배로 는다.
# 여기 없는 모델에는 보내지 않는다. 이 값을 받지 않는 모델도 있다.
_생각_끄기: dict[str, dict[str, Any]] = {
    # enable_thinking 은 DashScope 에 직접 부를 때만 통하고 게이트웨이를 거치면 무시된다.
    # reasoning_effort 는 양쪽에서 통한다.
    "qwen3.8-flash": {"reasoning_effort": "none"},
}


class _OpenAIChat:
    """OpenAI 호환 주소로 모델 하나를 부른다."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def call(
        self,
        system: str,
        user: str,
        *,
        response_json: bool = False,
        temperature: float = 0.0,
        timeout: Optional[float] = None,
    ) -> tuple[str, int, int]:
        """한 번 부르고 답, 입력 토큰 수, 출력 토큰 수를 돌려준다."""
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
        if timeout is not None:
            kwargs["timeout"] = timeout
        kwargs.update(_생각_끄기.get(self._model, {}))
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or "", *token_counts(getattr(resp, "usage", None))


class LLMClient:
    """채팅 호출 래퍼. 동기 SDK를 to_thread로 감싸 async 노출."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        role: Optional[LLMRole] = None,
    ) -> None:
        # 모델 이름을 보고 부르는 방법을 고른다
        if is_claude(model):
            self._호출 = ClaudeChat(model, base_url, api_key)
        elif is_gemini(model) and not base_url:
            # 주소 없이 온 Gemini 는 Vertex AI 로 부른다. 키 대신 프로젝트와 위치를 쓴다
            self._호출 = VertexChat(model, settings.GOOGLE_CLOUD_PROJECT, settings.GOOGLE_CLOUD_LOCATION)
        else:
            self._호출 = _OpenAIChat(model, base_url, api_key)
        self._model = model
        # 기록에 남길 역할 이름. 역할 없이 직접 만든 클라이언트면 비워 둔다.
        self._role = role.value if role is not None else ""

    async def chat(
        self,
        system: str,
        user: str,
        response_json: bool = False,
        temperature: float = 0.0,
        timeout: Optional[float] = None,
    ) -> str:
        """
        채팅 호출.

        response_json=True면 JSON 으로만 답하게 하고(OpenAI 호환 주소는
        response_format 을 json_object 로 강제) 파싱 가능한 JSON 문자열만 반환.
        timeout(초)을 주면 요청 하나에 그 시간만 기다린다. 비우면 SDK 기본값.

        Claude 는 response_json 과 temperature 를 받지 않아 보내지 않는다.
        Vertex AI 의 Gemini 에는 temperature 를 보내지 않는다.

        성공하든 실패하든 호출 기록을 하나 남긴다. 실패한 호출도 시간을 썼고,
        빼면 느린 쪽 시간이 실제보다 좋게 나온다.
        """
        시작 = time.perf_counter()
        try:
            내용, 입력, 출력 = await asyncio.to_thread(
                self._호출.call,
                system,
                user,
                response_json=response_json,
                temperature=temperature,
                timeout=timeout,
            )
        except (Exception, asyncio.CancelledError):
            # 취소는 Exception 이 아니라 따로 잡는다. 빼면 이미 쓴 시간이 기록에서 빠진다
            self._기록(시작, 0, 0, ok=False)
            raise
        self._기록(시작, 입력, 출력, ok=True)
        return 내용

    def _기록(self, 시작: float, 입력: int, 출력: int, ok: bool) -> None:
        record(LLMCall(
            role=self._role,
            model=self._model,
            input_tokens=입력,
            output_tokens=출력,
            seconds=time.perf_counter() - 시작,
            ok=ok,
        ))

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """JSON 응답 호출 + 파싱. 파싱 실패 시 None."""
        raw = await self.chat(system, user, response_json=True, temperature=temperature, timeout=timeout)
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
    return LLMClient(model=모델, base_url=주소, api_key=키, role=role)