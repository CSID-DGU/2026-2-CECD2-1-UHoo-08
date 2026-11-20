"""모델 비교 실험의 후보 모델.

역할(Normalize, Weight, Compose)에 쓸 모델을 바꿔 가며 같은 문제를 태울 때,
후보마다 어디로 부르는지와 다른 모델과 다르게 다루는 설정을 한곳에 적어 둔다.
평가 도구는 이 목록을 보고 역할의 모델 설정을 바꿔 끼운다.

    from eval.model_candidates import use_candidate
    from services.llm import LLMRole

    with use_candidate(LLMRole.NORMALIZE, "claude-haiku-5-5"):
        ...  # 이 안에서 get_llm(LLMRole.NORMALIZE) 는 후보 모델을 부른다

바꿔 끼우는 값은 서비스가 읽는 역할 설정(LLM_역할_MODEL, BASE_URL, API_KEY)과
같다. 그래서 실험에서 고른 모델은 같은 값을 환경 변수로 넣기만 하면 서비스에 쓸 수 있다.

가격은 eval/router_metrics.py 의 가격표에 적는다. 후보를 더하면 거기에도 더한다.

모델마다 다르게 다루는 설정(temperature, 생각 기능, JSON 응답)은 services/llm 의
호출 코드가 정한다. 여기에는 리포트에 적을 말만 둔다. 호출 코드를 고치면 함께 고친다.

config 와 services.llm 은 함수 안에서 가져온다. 최상단에서 가져오면 API 키를
요구해, 키 없는 곳에서는 후보 목록도 읽지 못한다.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from services.llm.client import LLMRole


@dataclass(frozen=True)
class Candidate:
    model: str            # 모델 이름. 역할의 MODEL 설정에 그대로 넣는다
    place: str            # 부르는 곳
    temperature: str      # 부르는 쪽이 준 temperature 를 어떻게 하는가
    thinking: str         # 생각 기능을 어떻게 맞췄는가
    json_mode: str        # JSON 으로만 답하게 하는 방법
    # 주소와 키를 따로 줘야 하면 그 값을 가진 설정 이름. 비우면 모델을 보고 정한 기본값을 쓴다
    base_url_from: str = ""
    api_key_from: str = ""

    def describe(self) -> str:
        """리포트 머리말에 적을 한 줄."""
        return f"temperature {self.temperature}, 생각 기능 {self.thinking}, JSON 응답 {self.json_mode}"


# 지금 서비스가 쓰는 모델. 다른 후보는 이 모델과 견준다
CURRENT = "qwen-plus"

# JSON 응답은 모델이 주는 방법 중 가장 강한 것을 쓴다. Qwen 과 Gemini 는 JSON 으로만 답하게 하는
# 옵션이고, Claude 는 답의 스키마까지 강제한다. Claude 는 스키마를 넘기지 않는 역할에서는
# 프롬프트로만 양식을 지킨다
_후보들 = (
    Candidate("qwen-plus", "DashScope",
              temperature="그대로 보냄", thinking="기본으로 꺼져 있음", json_mode="API 옵션"),
    # DashScope 에도 있는 모델이지만 실험에서는 학교 게이트웨이의 크레딧으로 부른다.
    # 게이트웨이를 한 번 더 거치므로 시간은 DashScope 에 직접 부를 때보다 길게 나온다
    Candidate("qwen3.8-flash", "동국 AI Gateway",
              temperature="그대로 보냄", thinking="끔", json_mode="API 옵션",
              base_url_from="QWEN_GATEWAY_BASE_URL", api_key_from="QWEN_GATEWAY_API_KEY"),
    Candidate("claude-haiku-5-5", "Anthropic API",
              temperature="보내지 않음 (받지 않는 모델)", thinking="끔", json_mode="스키마로 강제 (구조화 출력)"),
    Candidate("claude-sonnet-5-5", "Anthropic API",
              temperature="보내지 않음 (받지 않는 모델)", thinking="끔", json_mode="스키마로 강제 (구조화 출력)"),
    Candidate("gemini-3.5-flash-lite", "Vertex AI",
              temperature="보내지 않음 (기본값 권장)", thinking="가장 낮은 단계 (MINIMAL)", json_mode="API 옵션"),
    Candidate("gemini-3.8-flash", "Vertex AI",
              temperature="보내지 않음 (기본값 권장)", thinking="가장 낮은 단계 (LOW)", json_mode="API 옵션"),
    Candidate("gemini-3.1-pro-preview", "Vertex AI",
              temperature="보내지 않음 (기본값 권장)", thinking="가장 낮은 단계 (LOW)", json_mode="API 옵션"),
)

CANDIDATES: dict[str, Candidate] = {후보.model: 후보 for 후보 in _후보들}


def _설정_값(settings, 이름: str) -> str:
    """후보가 가리키는 설정의 값. 비어 있으면 빈 값으로 부르지 않고 여기서 멈춘다."""
    if not 이름:
        return ""
    값 = getattr(settings, 이름, "")
    if not 값:
        raise RuntimeError(f"{이름} 이 비어 있다. AI/.env 에 넣는다")
    return 값


@contextmanager
def use_candidate(role: "LLMRole", model: str) -> Iterator[Candidate]:
    """역할 하나의 모델을 후보로 바꿔 끼운다. 범위를 벗어나면 원래 설정으로 돌린다."""
    from config import settings
    from services.llm.client import get_llm

    if model not in CANDIDATES:
        raise KeyError(f"후보에 없는 모델이다: {model}. eval/model_candidates.py 참고")
    후보 = CANDIDATES[model]
    새_값 = {
        f"LLM_{role.name}_MODEL": 후보.model,
        f"LLM_{role.name}_BASE_URL": _설정_값(settings, 후보.base_url_from),
        f"LLM_{role.name}_API_KEY": _설정_값(settings, 후보.api_key_from),
    }
    원래_값 = {이름: getattr(settings, 이름) for 이름 in 새_값}

    def 넣기(값들: dict[str, str]) -> None:
        for 이름, 값 in 값들.items():
            setattr(settings, 이름, 값)
        # 역할마다 클라이언트를 하나 만들어 두고 다시 쓰므로, 비워야 새 설정으로 다시 만든다
        get_llm.cache_clear()

    넣기(새_값)
    try:
        yield 후보
    finally:
        넣기(원래_값)
