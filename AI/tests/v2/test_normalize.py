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


def _단서가_없다(spec: dict) -> bool:
    """라우터가 되묻기로 넘길 빈 값인가."""
    from contracts.query_spec import QuerySpec
    from rules.clarify import is_underspecified

    return is_underspecified(QuerySpec.model_validate(spec))


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
async def test_문자열_null은_빈_값으로_읽고_다시_묻지_않는다(LLM세우기):
    """그대로 두면 두 번 다 카테고리 검증에 실패해 되묻기로 넘어가고 예산과 세트를 잃는다."""
    가짜 = LLM세우기([{
        "request_type": "BUNDLE", "category": "null", "base_product_ref": "NULL",
        "budget": {"max": "null", "total": 100000},
        "bundle_steps": [{"category": "sun", "product_type": "선크림", "label": "선크림"},
                         {"category": "base", "product_type": "null", "label": "쿠션"}],
        "features": {"finish": "null"}, "conditions": ["null", "여름"],
    }])
    spec = (await 모듈.normalize({"raw_query": "10만원으로 선크림이랑 쿠션 세트"}))["query_spec"]
    assert 가짜.호출 == 1
    assert spec["category"] is None and spec["base_product_ref"] is None
    assert spec["budget"] == {"max": None, "total": 100000}
    assert [단계["product_type"] for 단계 in spec["bundle_steps"]] == ["선크림", None]
    assert spec["features"] == {} and spec["conditions"] == ["여름"]


@pytest.mark.asyncio
async def test_null만_든_종류_배열은_특징에서_빼고_다시_묻지_않는다(LLM세우기):
    """빈 목록으로 남기면 형식 오류로 다시 묻고, 두 번 받으면 예산과 세트를 잃는다."""
    가짜 = LLM세우기([{
        "request_type": "BUNDLE", "category": "skincare",
        "budget": {"max": None, "total": 100000},
        "bundle_steps": [{"category": "skincare", "product_type": "토너", "label": "토너"}],
        "features": {"product_type": ["null"]},
    }])
    spec = (await 모듈.normalize({"raw_query": "10만원으로 토너 세트"}))["query_spec"]
    assert 가짜.호출 == 1
    assert spec["features"] == {} and spec["budget"]["total"] == 100000


@pytest.mark.asyncio
async def test_null이_아닌_글자는_그대로_둔다(LLM세우기):
    LLM세우기([{**_제대로, "conditions": ["nullable", "논 코메도제닉"]}])
    spec = (await 모듈.normalize({"raw_query": "쿠션"}))["query_spec"]
    assert spec["category"] == "base"
    assert spec["conditions"] == ["nullable", "논 코메도제닉"]


@pytest.mark.asyncio
async def test_두_번_어기면_되묻기로_넘긴다(LLM세우기):
    """예외로 올리면 서버 오류가 된다. 되물을 수 있는 상태로 내보낸다."""
    가짜 = LLM세우기([{"request_type": "NOPE"}, {"category": "없는것"}])
    나온 = await 모듈.normalize({"raw_query": "이상한 질의"})
    assert 가짜.호출 == 2
    assert _단서가_없다(나온["query_spec"])


@pytest.mark.asyncio
async def test_이미_물은_뒤에_또_어기면_질의를_문장_조건으로_넣는다(LLM세우기):
    """라우터가 더 묻지 않고 진행하므로, 검색 문장에 쓸 것은 남겨 둔다."""
    LLM세우기([{"request_type": "NOPE"}, {"category": "없는것"}])
    나온 = await 모듈.normalize({"raw_query": "이상한 질의", "clarify_count": 1})
    assert 나온["query_spec"]["conditions"] == ["이상한 질의"]


@pytest.mark.asyncio
async def test_조건_수정에서_어기면_질의를_문장_조건으로_넣는다(LLM세우기):
    """조건 수정은 이전 질의가 있어 되묻지 않는다. 원문을 버리면 수정 조건이 사라진다."""
    LLM세우기([{"request_type": "NOPE"}, {"category": "없는것"}])
    나온 = await 모듈.normalize({"raw_query": "더 촉촉한 걸로", "parent_job_id": "prev"})
    assert 나온["query_spec"]["conditions"] == ["더 촉촉한 걸로"]


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
    assert _단서가_없다(나온["query_spec"])


@pytest.mark.asyncio
async def test_되물은_답을_원래_질의와_함께_읽는다(LLM세우기):
    """답만 주면 "10만원" 같은 말이 무슨 뜻인지 알 수 없다."""
    받은 = {}

    class 기록하는LLM(가짜LLM):
        async def chat_json(self, system, user, **kwargs):
            받은["user"] = user
            return await super().chat_json(system, user, **kwargs)

    가짜 = LLM세우기([_제대로])
    가짜.__class__ = 기록하는LLM

    await 모듈.normalize({
        "raw_query": "스킨케어 세트 짜줘",
        "clarify_question": "전체 예산이 얼마인가요?",
        "clarify_answer": "10만원",
    })

    assert "스킨케어 세트 짜줘" in 받은["user"]
    assert "전체 예산" in 받은["user"]
    assert "10만원" in 받은["user"]


@pytest.mark.asyncio
async def test_출력_양식_스키마를_함께_넘긴다(LLM세우기):
    """스키마로 답의 모양을 강제하는 모델이 이 스키마를 쓴다."""
    from prompts.query_normalize import QUERY_SPEC_SCHEMA

    받은 = {}

    class 기록하는LLM(가짜LLM):
        async def chat_json(self, system, user, **kwargs):
            받은.update(kwargs)
            return await super().chat_json(system, user, **kwargs)

    가짜 = LLM세우기([_제대로])
    가짜.__class__ = 기록하는LLM

    await 모듈.normalize({"raw_query": "여름 쿠션"})

    assert 받은["schema"] is QUERY_SPEC_SCHEMA


@pytest.mark.asyncio
async def test_답이_없으면_질의만_넘긴다(LLM세우기):
    """원래 질의에 군더더기가 붙으면 모델이 그것까지 조건으로 읽는다."""
    받은 = {}

    class 기록하는LLM(가짜LLM):
        async def chat_json(self, system, user, **kwargs):
            받은["user"] = user
            return await super().chat_json(system, user, **kwargs)

    가짜 = LLM세우기([_제대로])
    가짜.__class__ = 기록하는LLM

    await 모듈.normalize({"raw_query": "여름 쿠션"})
    assert 받은["user"] == "여름 쿠션"


def _종류_응답(category, product_type, **값):
    return {"request_type": "SEARCH", "category": category,
            "features": {"product_type": product_type}, **값}


@pytest.mark.asyncio
@pytest.mark.parametrize("category, 값, 표준", [
    ("skincare", "스킨", "토너"),
    ("sun", "선 세럼", "선에센스"),
    ("skincare", "크림", "크림"),
    ("eye", "아이라이너", "아이라이너"),
    (None, "블러쉬", "블러셔"),
])
async def test_제품_종류를_표준_이름으로_바꾼다(LLM세우기, category, 값, 표준):
    LLM세우기([_종류_응답(category, 값)])
    spec = (await 모듈.normalize({"raw_query": "질의"}))["query_spec"]
    assert spec["features"]["product_type"] == 표준


@pytest.mark.asyncio
async def test_목록에_없는_종류는_문장_조건으로_옮긴다(LLM세우기):
    """특징에 두면 필터가 맞는 상품을 하나도 남기지 않는다."""
    LLM세우기([_종류_응답("skincare", "핸드크림", conditions=["보습"])])
    spec = (await 모듈.normalize({"raw_query": "보습 핸드크림"}))["query_spec"]
    assert "product_type" not in spec["features"]
    assert spec["conditions"] == ["보습", "핸드크림"]


@pytest.mark.asyncio
async def test_카테고리에_맞지_않는_종류도_문장_조건으로_옮긴다(LLM세우기):
    LLM세우기([_종류_응답("skincare", "쿠션")])
    spec = (await 모듈.normalize({"raw_query": "쿠션"}))["query_spec"]
    assert "product_type" not in spec["features"]
    assert spec["conditions"] == ["쿠션"]


@pytest.mark.asyncio
@pytest.mark.parametrize("값, 특징, 조건", [
    (["스킨"], {"product_type": "토너"}, []),
    (["핸드크림"], {}, ["핸드크림"]),
])
async def test_하나만_든_배열은_풀어서_같은_규칙을_적용한다(LLM세우기, 값, 특징, 조건):
    """건너뛰면 종류가 필터와 검색 문장에서 모두 사라진 채 성공으로 나간다."""
    가짜 = LLM세우기([_종류_응답("skincare", 값)])
    spec = (await 모듈.normalize({"raw_query": "질의"}))["query_spec"]
    assert 가짜.호출 == 1
    assert spec["features"] == 특징 and spec["conditions"] == 조건


@pytest.mark.asyncio
@pytest.mark.parametrize("값", [["토너", "크림"], [], 3, {"이름": "토너"}])
async def test_문자열_하나로_맞출_수_없는_종류는_다시_묻는다(LLM세우기, 값):
    가짜 = LLM세우기([_종류_응답("skincare", 값), _종류_응답("skincare", "스킨")])
    spec = (await 모듈.normalize({"raw_query": "질의"}))["query_spec"]
    assert 가짜.호출 == 2
    assert spec["features"]["product_type"] == "토너"


@pytest.mark.asyncio
async def test_종류_형식을_두_번_어기면_되묻기로_넘긴다(LLM세우기):
    LLM세우기([_종류_응답("skincare", ["토너", "크림"])] * 2)
    spec = (await 모듈.normalize({"raw_query": "질의"}))["query_spec"]
    assert _단서가_없다(spec)


@pytest.mark.asyncio
async def test_종류가_비어_있으면_특징에서_뺀다(LLM세우기):
    LLM세우기([_종류_응답("base", None)])
    spec = (await 모듈.normalize({"raw_query": "베이스"}))["query_spec"]
    assert spec["features"] == {}
    assert spec["conditions"] == []


@pytest.mark.asyncio
async def test_세트_단계의_종류도_바꾸고_모르면_비운다(LLM세우기):
    LLM세우기([{
        "request_type": "BUNDLE", "category": "skincare",
        "budget": {"max": None, "total": 100000},
        "bundle_steps": [
            {"category": "skincare", "product_type": "스킨", "label": "스킨"},
            {"category": "skincare", "product_type": "핸드크림", "label": "핸드크림"},
        ],
    }])
    spec = (await 모듈.normalize({"raw_query": "10만원으로 스킨, 핸드크림"}))["query_spec"]
    assert [단계["product_type"] for 단계 in spec["bundle_steps"]] == ["토너", None]
    assert [단계["label"] for 단계 in spec["bundle_steps"]] == ["스킨", "핸드크림"]


@pytest.mark.asyncio
async def test_카테고리의_특징_표에_없는_키는_버린다(LLM세우기):
    """스키마는 모든 카테고리의 키를 열어 두므로, 스킨케어에 waterproof 가 올 수 있다."""
    LLM세우기([{**_제대로, "category": "skincare", "conditions": [],
                "features": {"product_type": "크림", "texture": "가벼운", "waterproof": False}}])
    spec = (await 모듈.normalize({"raw_query": "여름용 산뜻한 수분크림"}))["query_spec"]
    assert spec["features"] == {"product_type": "크림", "texture": "가벼운"}
    # 사용자가 말한 조건이 아니므로 문장 조건으로도 옮기지 않는다
    assert spec["conditions"] == []


@pytest.mark.asyncio
async def test_카테고리를_모르면_어느_카테고리의_키든_남긴다(LLM세우기):
    LLM세우기([{**_제대로, "category": None, "features": {"waterproof": True}}])
    spec = (await 모듈.normalize({"raw_query": "워터프루프"}))["query_spec"]
    assert spec["features"] == {"waterproof": True}
