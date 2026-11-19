"""Claude 호출 (Anthropic SDK).

역할의 모델 이름이 claude- 로 시작하면 LLMClient 가 OpenAI 호환 주소 대신
여기로 보낸다. 부르는 쪽은 차이를 몰라도 된다.

Claude 에도 OpenAI 호환 주소가 있지만 쓰지 않는다. 그 주소에서는 생각 기능을
조절할 수 없어 짧은 답에도 시간과 토큰이 더 들고, Anthropic 도 그 주소는 시험과
비교용이라고 안내한다.

다른 모델과 다르게 다루는 것이 셋 있다.

temperature 는 보내지 않는다. 지금 모델들은 이 값을 받지 않는다.

JSON 으로만 답하라는 옵션도 보내지 않는다. Claude 는 스키마를 함께 줘야 양식을
강제할 수 있는데 스키마는 역할마다 다르다. 양식은 프롬프트로 지키게 한다.

생각 기능은 끈다. 기본으로 켜져 있지만 역할들이 맡기는 일은 짧은 변환과 문장
쓰기이고, 사용자가 기다리는 동안 부른다. 끄는 값은 모델마다 달라 표로 둔다.

anthropic 패키지는 부를 일이 생긴 뒤에 가져온다. Claude 를 쓰지 않는 곳에서는
설치하지 않아도 이 모듈을 불러올 수 있다.
"""
from __future__ import annotations

from typing import Any, Optional

# 주소를 직접 적어 둔다. 비워 두면 SDK 가 ANTHROPIC_BASE_URL 환경 변수를 읽는데,
# 개발 도구가 그 값을 다른 곳으로 잡아 두는 일이 있다.
DEFAULT_BASE_URL = "https://api.anthropic.com"

# 답 길이의 상한. Claude 는 이 값을 꼭 받는다. 역할들의 답은 짧은 JSON 이라 넉넉하다.
_최대_출력_토큰 = 4096

# 생각 기능을 끄는 값. 모델마다 받는 값이 다르다.
# 여기 없는 모델은 값을 보내지 않아 그 모델의 기본 동작을 따른다.
_생각_끄기: dict[str, dict[str, str]] = {
    "claude-haiku-5-5": {"type": "disabled"},
    "claude-sonnet-5-5": {"type": "between_tools"},
}


def is_claude(model: str) -> bool:
    """Anthropic SDK 로 불러야 하는 모델인가."""
    return model.startswith("claude-")


def _토큰_수(usage: Any) -> tuple[int, int]:
    """응답의 usage 에서 입력, 출력 토큰 수를 꺼낸다. 읽지 못한 값은 0 으로 본다.

    입력에는 캐시에 쓴 토큰과 캐시에서 읽은 토큰을 더한다. 응답이 셋을 따로
    세어 주므로 빼면 프롬프트가 실제보다 작게 남는다.
    """
    def _수(이름: str) -> int:
        값 = getattr(usage, 이름, None)
        return 값 if isinstance(값, int) else 0

    입력 = _수("input_tokens") + _수("cache_creation_input_tokens") + _수("cache_read_input_tokens")
    return 입력, _수("output_tokens")


class ClaudeChat:
    """Claude 모델 하나를 부른다. LLMClient 가 만들어 쓴다."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        if not api_key:
            # 빈 값으로 넘기면 SDK 가 환경에 있는 다른 인증 정보를 찾아 쓴다
            raise RuntimeError("ANTHROPIC_API_KEY 가 비어 있다. AI/.env 에 넣는다")
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, base_url=base_url or DEFAULT_BASE_URL)
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
        """한 번 부르고 답, 입력 토큰 수, 출력 토큰 수를 돌려준다.

        response_json 과 temperature 는 받기만 하고 보내지 않는다.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _최대_출력_토큰,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            kwargs["system"] = system
        생각 = _생각_끄기.get(self._model)
        if 생각 is not None:
            kwargs["thinking"] = 생각
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = self._client.messages.create(**kwargs)
        # 답 앞에 생각 블록이 올 수 있어 종류를 보고 글만 모은다.
        # 모델이 답을 거절하면 글이 없어 빈 문자열이 된다.
        내용 = "".join(b.text for b in resp.content if b.type == "text")
        return 내용, *_토큰_수(resp.usage)
