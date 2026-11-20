"""Gemini 호출 (Vertex AI).

역할의 모델 이름이 gemini- 로 시작하는데 주소를 따로 주지 않았으면 LLMClient 가
여기로 보낸다. 주소를 줬으면 전처럼 OpenAI 호환 주소로 부른다.

Vertex AI 는 API 키 대신 구글 클라우드 프로젝트와 로그인 정보로 부른다. 로컬에서는
gcloud auth application-default login 으로 로그인해 둔 계정을 쓴다.

OpenAI 호환 주소로 부를 때와 다르게 다루는 것이 둘 있다.

temperature 는 보내지 않는다. Gemini 3 부터는 기본값으로 두라고 안내한다. 낮추면
같은 말을 되풀이하거나 품질이 떨어질 수 있다고 한다.

생각 기능은 가장 낮은 단계로 맞춘다. Gemini 3 부터는 끌 수 없고 단계만 고른다.
고를 수 있는 단계가 모델마다 달라 표로 둔다.

google-genai 패키지는 부를 일이 생긴 뒤에 가져온다.
"""
from __future__ import annotations

from typing import Any, Optional

# 가장 낮은 생각 단계. 모델이 받지 않는 단계를 보내면 오류가 난다.
# 여기 없는 모델은 값을 보내지 않아 그 모델의 기본 동작을 따른다.
_가장_낮은_생각: dict[str, str] = {
    "gemini-3.5-flash-lite": "MINIMAL",
    "gemini-3.8-flash": "LOW",
    "gemini-3.1-pro-preview": "LOW",
}

# 잠깐의 오류(요청이 몰림, 서버 오류)는 두 번까지 다시 보낸다. 이 SDK 는 따로 정하지
# 않으면 다시 보내지 않는다. OpenAI, Anthropic SDK 는 기본으로 두 번 다시 보내므로
# 그대로 두면 Gemini 만 실패가 많게 잡힌다.
_시도_횟수 = 3


def is_gemini(model: str) -> bool:
    """Gemini 모델인가. 주소 없이 고르면 Vertex AI 로 부른다."""
    return model.startswith("gemini-")


def _토큰_수(usage: Any) -> tuple[int, int]:
    """응답의 usage 에서 입력, 출력 토큰 수를 꺼낸다. 읽지 못한 값은 0 으로 본다.

    출력에는 생각에 쓴 토큰을 더한다. 답과 따로 세어 주지만 값은 출력으로 매긴다.
    """
    def _수(이름: str) -> int:
        값 = getattr(usage, 이름, None)
        return 값 if isinstance(값, int) else 0

    return _수("prompt_token_count"), _수("candidates_token_count") + _수("thoughts_token_count")


def _글(resp: Any) -> str:
    """응답에서 답 글만 모은다. 답이 막히면 후보가 없어 빈 문자열이 된다.

    resp.text 는 쓰지 않는다. 글이 아닌 조각이 섞여 있으면 호출마다 경고를 남긴다.
    """
    후보들 = getattr(resp, "candidates", None) or []
    if not 후보들:
        return ""
    조각들 = getattr(getattr(후보들[0], "content", None), "parts", None) or []
    return "".join(
        조각.text for 조각 in 조각들
        if isinstance(getattr(조각, "text", None), str) and getattr(조각, "thought", None) is not True
    )


class VertexChat:
    """Vertex AI 의 Gemini 모델 하나를 부른다. LLMClient 가 만들어 쓴다."""

    def __init__(self, model: str, project: str, location: str) -> None:
        if not project or not location:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT 나 GOOGLE_CLOUD_LOCATION 이 비어 있다. AI/.env 에 넣는다"
            )
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=_시도_횟수),
            ),
        )
        self._model = model

    def call(
        self,
        system: str,
        user: str,
        *,
        response_json: bool = False,
        temperature: float = 0.0,
        timeout: Optional[float] = None,
        schema: Optional[dict[str, Any]] = None,
    ) -> tuple[str, int, int]:
        """한 번 부르고 답, 입력 토큰 수, 출력 토큰 수를 돌려준다.

        temperature 와 schema 는 받기만 하고 보내지 않는다. 양식은 JSON 응답 옵션으로 지키게 한다.
        """
        types = self._types
        설정: dict[str, Any] = {}
        if system:
            설정["system_instruction"] = system
        if response_json:
            설정["response_mime_type"] = "application/json"
        단계 = _가장_낮은_생각.get(self._model)
        if 단계 is not None:
            설정["thinking_config"] = types.ThinkingConfig(thinking_level=단계)
        if timeout is not None:
            # 이 SDK 는 기다리는 시간을 밀리초로 받는다
            설정["http_options"] = types.HttpOptions(timeout=int(timeout * 1000))
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(**설정),
        )
        return _글(resp), *_토큰_수(getattr(resp, "usage_metadata", None))
