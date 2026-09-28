"""Normalize 가 지켜야 할 성질.

LLM 출력은 언제든 형식을 어긴다. 어겼을 때 무엇을 하느냐가 이 노드의 거의
전부다. 그냥 통과시키면 사용자가 요청하지 않은 조건으로 걸러진 결과가
그대로 나가고, 예외로 올리면 "무슨 말인지 모르겠다"가 서버 오류가 된다.
"""
import pytest

from graph.nodes import normalize as 모듈


class 가짜LLM:
    def __init__(self, 응답들):
        self.응답들 = list(응답들)
        self.호출 = 0

    async def chat_json(self, system, user, **kwargs):
        self.호출 += 1
        return self.응답들.pop(0) if self.응답들 else None


@pytest.fixture
def LLM세우기(monkeypatch):
    import sys
    import types

    def 세우기(응답들):
        가짜 = 가짜LLM(응답들)
        모듈_대역 = types.SimpleNamespace(
            LLMRole=types.SimpleNamespace(NORMALIZE="normalize"),
            get_llm=lambda role: 가짜,
        )
        import services
        monkeypatch.setitem(sys.modules, "services.llm", 모듈_대역)
        monkeypatch.setattr(services, "llm", 모듈_대역, raising=False)
        return 가짜

    return 세우기


_제대로 = {
    "request_type": "SEARCH", "category": "base",
    "budget": {"max": 30000, "total": None},
    "features": {"finish": "세미매트"}, "conditions": ["여름"],
    "confidence": 0.9,
}


@pytest.mark.asyncio
async def test_해석한_값을_스펙으로_내보낸다(LLM세우기):
    LLM세우기([_제대로])
    나온 = await 모듈.normalize({"raw_query": "여름에 안 무너지는 세미매트 쿠션 3만원 이하"})
    spec = 나온["query_spec"]
    assert spec["category"] == "base"
    assert spec["budget"]["max"] == 30000
    assert spec["features"]["finish"] == "세미매트"


@pytest.mark.asyncio
async def test_형식을_어기면_한_번_다시_묻는다(LLM세우기):
    가짜 = LLM세우기([{"request_type": "NOPE"}, _제대로])
    나온 = await 모듈.normalize({"raw_query": "쿠션"})
    assert 가짜.호출 == 2
    assert 나온["query_spec"]["category"] == "base"


@pytest.mark.asyncio
async def test_두_번_어기면_되묻기로_넘긴다(LLM세우기):
    """예외로 올리면 서버 오류가 된다. 되물을 수 있는 상태로 내보낸다."""
    가짜 = LLM세우기([{"request_type": "NOPE"}, {"category": "없는것"}])
    나온 = await 모듈.normalize({"raw_query": "이상한 질의"})
    assert 가짜.호출 == 2
    assert 나온["query_spec"]["confidence"] == 0.0
    assert 나온["query_spec"]["conditions"] == ["이상한 질의"]


@pytest.mark.asyncio
async def test_세_번_이상_묻지_않는다(LLM세우기):
    """형식을 두 번 어긴 모델이 세 번째에 지킬 가능성은 낮고,
    그동안 사용자는 계속 기다린다."""
    가짜 = LLM세우기([None, None, _제대로])
    await 모듈.normalize({"raw_query": "쿠션"})
    assert 가짜.호출 == 2


@pytest.mark.asyncio
async def test_모르는_필드를_붙이면_다시_묻는다(LLM세우기):
    """조용히 무시하면 모델이 계속 그 필드를 만든다."""
    틀린 = dict(_제대로, skin_type="DRY")
    가짜 = LLM세우기([틀린, _제대로])
    await 모듈.normalize({"raw_query": "쿠션"})
    assert 가짜.호출 == 2


@pytest.mark.asyncio
async def test_빈_질의는_부르지도_않는다(LLM세우기):
    가짜 = LLM세우기([_제대로])
    나온 = await 모듈.normalize({"raw_query": "   "})
    assert 가짜.호출 == 0
    assert 나온["query_spec"]["confidence"] == 0.0
