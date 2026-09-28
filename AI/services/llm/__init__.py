"""역할별 LLM 클라이언트.

모델을 부르는 쪽에 박아 두지 않고 역할로 부른다. 그래야 "Normalize 만 상위
모델로 올리면 정확도가 얼마나 오르는지" 같은 비교를 코드 수정 없이 할 수
있고, 비용 대비 효과가 큰 곳만 골라 올릴 수 있다.

    from services.llm import LLMRole, get_llm

    llm = get_llm(LLMRole.NORMALIZE)
    spec = await llm.chat_json(system=..., user=...)
"""
from services.llm.client import LLMClient, LLMRole, get_llm

__all__ = ["LLMClient", "LLMRole", "get_llm"]
