"""빌더가 지켜야 할 성질.

노드가 아직 하나도 없는 상태에서도 경로가 끝까지 돌아야 한다. 그래야 각
파트가 자기 노드만 채워 넣으면서 진행 상황을 볼 수 있다.
"""
import pytest

from graph import builder
from graph.builder import build, run_scenario


@pytest.mark.asyncio
async def test_노드가_하나도_없어도_끝까지_돈다():
    결과 = await run_scenario("S2_SEARCH", {"job_id": "j1", "user_id": "u1"})
    assert [단계.removesuffix("(stub)") for 단계 in 결과["trace"]] == [
        "retrieve", "inventory", "prefilter", "score", "collaborative", "compose", "guard",
    ]


@pytest.mark.asyncio
async def test_아직_없는_노드임을_trace에_표시한다():
    """전부 돌았다는 것과 전부 비어 있다는 것은 다르다. 표시가 없으면
    빈 결과를 정상으로 읽게 된다."""
    결과 = await run_scenario("S2_SEARCH")
    assert all(단계.endswith("(stub)") for 단계 in 결과["trace"])


@pytest.mark.asyncio
async def test_기본은_관문을_건너뛴다():
    """QuerySpec 을 직접 넣어 원하는 경로만 확인하는 것이 이 함수의 쓰임이다."""
    결과 = await run_scenario("S2_SEARCH")
    assert not any(단계.startswith("normalize") for 단계 in 결과["trace"])

    포함 = await run_scenario("S2_SEARCH", include_entry=True)
    assert 포함["trace"][0].startswith("normalize")


@pytest.mark.asyncio
async def test_환경_요청이면_집계_단계가_돈다():
    결과 = await run_scenario("S2_SEARCH", {"query_spec": {"use_env": True}})
    assert "env_history(stub)" in 결과["trace"]


@pytest.mark.asyncio
async def test_실제_노드의_반환이_상태에_합쳐진다(monkeypatch):
    async def retrieve(state):
        return {"candidates": [{"product_id": "p1", "source": "vector", "similarity": 0.9}]}

    monkeypatch.setattr(builder, "_load", lambda name: retrieve if name == "retrieve" else None)

    결과 = await run_scenario("S2_SEARCH")
    assert 결과["candidates"][0]["product_id"] == "p1"
    # 실제 노드는 stub 표시가 붙지 않는다
    assert "retrieve" in 결과["trace"] and "retrieve(stub)" not in 결과["trace"]


@pytest.mark.asyncio
async def test_노드가_터지면_알리고_그대로_올린다(monkeypatch):
    """노드 안에서 삼키고 빈 값을 넘기면 다음 노드가 0점을 계산해 내보내고,
    결과만 보면 정상으로 보인다."""
    async def 망가진(state):
        raise RuntimeError("벡터 검색 실패")

    monkeypatch.setattr(builder, "_load", lambda name: 망가진 if name == "retrieve" else None)

    받은: list[Exception] = []

    async def on_fail(e):
        받은.append(e)

    with pytest.raises(RuntimeError, match="벡터 검색 실패"):
        await run_scenario("S2_SEARCH", on_fail=on_fail)
    assert len(받은) == 1


@pytest.mark.asyncio
async def test_진행률은_단계_시작에_알리고_끝에_100이_된다():
    기록: list[tuple[str, int]] = []

    async def hook(문구, 비율, 단계들):
        기록.append((문구, 비율))

    await run_scenario("S2_SEARCH", on_progress=hook)

    assert 기록[0] == ("조건에 맞는 상품 찾기", 0)
    assert 기록[-1] == ("완료", 100)
    assert [비율 for _, 비율 in 기록] == sorted(비율 for _, 비율 in 기록)


@pytest.mark.asyncio
async def test_실패하면_100을_알리지_않는다(monkeypatch):
    """끝나지도 않았는데 완료로 보이면 화면이 빈 결과를 띄운다."""
    async def 망가진(state):
        raise RuntimeError("실패")

    monkeypatch.setattr(builder, "_load", lambda name: 망가진 if name == "retrieve" else None)
    기록: list[tuple[str, int]] = []

    async def hook(문구, 비율, 단계들):
        기록.append((문구, 비율))

    with pytest.raises(RuntimeError):
        await run_scenario("S2_SEARCH", on_progress=hook)
    assert ("완료", 100) not in 기록


def test_같은_단계가_두_번이면_바로_막는다(monkeypatch):
    """langgraph 는 같은 이름의 노드를 두 번 받지 못한다. 여기서 막지 않으면
    레지스트리를 고친 사람이 알아보기 어려운 오류를 본다."""
    monkeypatch.setattr(
        builder, "full_path", lambda s, use_env=False: ("retrieve", "score", "retrieve")
    )
    with pytest.raises(ValueError, match="두 번"):
        build("S2_SEARCH")


def test_모르는_시나리오는_예외다():
    with pytest.raises(KeyError):
        build("S9_NOPE")


@pytest.mark.asyncio
async def test_관문을_먼저_돌고_경로로_이어진다(monkeypatch):
    """라우터가 정한 시나리오로 경로가 조립돼야 한다."""
    async def router(state):
        return {"scenario": "S6_BUNDLE"}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)

    결과 = await builder.run_query({"raw_query": "10만원으로 세트"})
    assert 결과["scenario"] == "S6_BUNDLE"
    assert 결과["trace"][:2] == ["normalize(stub)", "router"]
    assert "bundle(stub)" in 결과["trace"]


@pytest.mark.asyncio
async def test_되물어야_하면_경로를_돌지_않는다(monkeypatch):
    """물어볼 것이 있는데 경로를 돌면, 답을 받기도 전에 엉뚱한 결과가 나온다."""
    async def router(state):
        return {"scenario": "S2_SEARCH", "clarify_question": "예산이 얼마인가요?"}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)

    결과 = await builder.run_query({"raw_query": "세트"})
    assert 결과["clarify_question"]
    assert 결과["trace"] == ["normalize(stub)", "router"]


@pytest.mark.asyncio
async def test_진행률이_관문에서_경로로_이어진다(monkeypatch):
    """관문을 돈 뒤 0 부터 다시 세면 화면의 막대가 뒤로 돌아간다."""
    monkeypatch.setattr(builder, "_load", lambda name: None)
    기록: list[int] = []

    async def hook(문구, 비율, 단계들):
        기록.append(비율)

    await builder.run_query({"raw_query": "쿠션"}, on_progress=hook)
    assert 기록 == sorted(기록)
    assert 기록[-1] == 100


@pytest.mark.asyncio
async def test_기준_상품이_있으면_관문_없이_평가_경로를_돈다(monkeypatch):
    """해석할 문장이 없으므로 LLM 도, 되묻기도 없어야 한다."""
    불린: list[str] = []

    def 찾기(이름):
        불린.append(이름)
        return None

    monkeypatch.setattr(builder, "_load", 찾기)

    결과 = await builder.run_query({"base_product_id": "p1", "raw_query": ""})

    assert 결과["scenario"] == "S1_EVALUATE"
    assert "normalize" not in 불린 and "router" not in 불린
    assert 결과["trace"][0] == "discovery(stub)"
    assert not 결과.get("clarify_question")


@pytest.mark.asyncio
async def test_기준_상품과_추천_기준을_해석_결과_자리에_채운다(monkeypatch):
    monkeypatch.setattr(builder, "_load", lambda name: None)

    결과 = await builder.run_query({"base_product_id": "p1", "basis": "POPULAR"})

    assert 결과["query_spec"]["request_type"] == "EVALUATE"
    assert 결과["query_spec"]["base_product_ref"] == "p1"
    assert 결과["query_spec"]["target"] == "POPULAR"


@pytest.mark.asyncio
async def test_기준_상품_평가의_단계_목록에_관문이_없다(monkeypatch):
    monkeypatch.setattr(builder, "_load", lambda name: None)
    기록: list[list[dict]] = []
    비율들: list[int] = []

    async def hook(문구, 비율, 단계들):
        기록.append(단계들)
        비율들.append(비율)

    await builder.run_query({"base_product_id": "p1"}, on_progress=hook)

    assert 기록[0][0] == {"key": "discovery", "label": builder.NODE_LABELS["discovery"], "state": "NOW"}
    assert {단계["key"] for 단계 in 기록[0]}.isdisjoint({"normalize", "router"})
    assert {단계["state"] for 단계 in 기록[-1]} == {"DONE"}
    assert 비율들 == sorted(비율들) and 비율들[-1] == 100


@pytest.mark.asyncio
async def test_기준_상품_평가가_실패하면_실패를_알리고_올린다(monkeypatch):
    async def 터짐(state):
        raise RuntimeError("없는 상품")

    monkeypatch.setattr(builder, "_load", lambda name: 터짐 if name == "discovery" else None)
    받은: list[Exception] = []

    async def 실패(e):
        받은.append(e)

    with pytest.raises(RuntimeError):
        await builder.run_query({"base_product_id": "p1"}, on_fail=실패)
    assert len(받은) == 1


def _상태들(단계들):
    return [(단계["key"], 단계["state"]) for 단계 in 단계들]


def test_단계_목록은_끝난_것_지금_것_남은_것을_나눈다():
    assert builder.단계_목록(("normalize", "router", "retrieve"), 1) == [
        {"key": "normalize", "label": "요청 이해", "state": "DONE"},
        {"key": "router", "label": "경로 결정", "state": "NOW"},
        {"key": "retrieve", "label": "조건에 맞는 상품 찾기", "state": "TODO"},
    ]


def test_단계_목록의_지금이_길이와_같으면_모두_끝난_것이다():
    assert _상태들(builder.단계_목록(("normalize", "router"), 2)) == [
        ("normalize", "DONE"), ("router", "DONE"),
    ]


@pytest.mark.asyncio
async def test_관문_동안에는_관문만_싣고_경로가_정해지면_이어서_싣는다(monkeypatch):
    """라우터를 지나기 전에는 어느 경로로 갈지 모른다."""
    async def router(state):
        return {"scenario": "S2_SEARCH"}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)
    기록: list[list[dict]] = []

    async def hook(문구, 비율, 단계들):
        기록.append(단계들)

    await builder.run_query({"raw_query": "쿠션"}, on_progress=hook)

    assert _상태들(기록[0]) == [("normalize", "NOW"), ("router", "TODO")]
    assert _상태들(기록[1]) == [("normalize", "DONE"), ("router", "NOW")]
    경로 = ["retrieve", "inventory", "prefilter", "score", "collaborative", "compose", "guard"]
    assert [단계["key"] for 단계 in 기록[2]] == ["normalize", "router", *경로]
    assert 기록[2][0]["state"] == "DONE" and 기록[2][1]["state"] == "DONE"
    assert 기록[2][2]["state"] == "NOW"
    assert {단계["state"] for 단계 in 기록[2][3:]} == {"TODO"}
    # 도는 동안 지금 단계는 하나이고, 끝나면 모두 DONE 이다
    assert all(sum(단계["state"] == "NOW" for 단계 in 단계들) == 1 for 단계들 in 기록[:-1])
    assert {단계["state"] for 단계 in 기록[-1]} == {"DONE"}
    assert len(기록[-1]) == 9


@pytest.mark.asyncio
async def test_되묻는_경로는_관문_단계에서_멈춘다(monkeypatch):
    async def router(state):
        return {"scenario": "S2_SEARCH", "clarify_question": "예산이 얼마인가요?"}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)
    기록: list[list[dict]] = []

    async def hook(문구, 비율, 단계들):
        기록.append(단계들)

    await builder.run_query({"raw_query": "세트"}, on_progress=hook)
    assert _상태들(기록[-1]) == [("normalize", "DONE"), ("router", "NOW")]


@pytest.mark.asyncio
async def test_실패하면_실패한_단계가_지금_단계로_남는다(monkeypatch):
    async def 망가진(state):
        raise RuntimeError("실패")

    monkeypatch.setattr(builder, "_load", lambda name: 망가진 if name == "inventory" else None)
    기록: list[list[dict]] = []

    async def hook(문구, 비율, 단계들):
        기록.append(단계들)

    with pytest.raises(RuntimeError):
        await run_scenario("S2_SEARCH", on_progress=hook)
    assert _상태들(기록[-1])[:2] == [("retrieve", "DONE"), ("inventory", "NOW")]


@pytest.mark.asyncio
async def test_관문이_끝나면_경로를_알린다(monkeypatch):
    async def router(state):
        return {"scenario": "S6_BUNDLE", "query_spec": {"category": "skincare"}}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)
    알림: list[dict] = []

    async def on_route(상태):
        # 경로를 돌기 전에 알려야 진행 중에도 시나리오가 보인다
        알림.append({"scenario": 상태["scenario"], "trace": list(상태["trace"])})

    await builder.run_query({"raw_query": "세트"}, on_route=on_route)
    assert 알림 == [{"scenario": "S6_BUNDLE", "trace": ["normalize(stub)", "router"]}]


@pytest.mark.asyncio
async def test_되묻는_경우에도_경로를_알린다(monkeypatch):
    async def router(state):
        return {"scenario": "S6_BUNDLE", "clarify_question": "예산이 얼마인가요?"}

    monkeypatch.setattr(builder, "_load", lambda name: router if name == "router" else None)
    알림: list[str] = []

    async def on_route(상태):
        알림.append(상태["scenario"])

    결과 = await builder.run_query({"raw_query": "세트"}, on_route=on_route)
    assert 결과["clarify_question"]
    assert 알림 == ["S6_BUNDLE"]


@pytest.mark.asyncio
async def test_라우터가_시나리오를_정하지_않으면_기본_경로를_알린다(monkeypatch):
    monkeypatch.setattr(builder, "_load", lambda name: None)
    알림: list[str] = []

    async def on_route(상태):
        알림.append(상태["scenario"])

    결과 = await builder.run_query({"raw_query": "쿠션"}, on_route=on_route)
    assert 알림 == [builder.기본_시나리오()]
    assert 결과["scenario"] == builder.기본_시나리오()


@pytest.mark.asyncio
async def test_기준_상품_경로도_알린다(monkeypatch):
    monkeypatch.setattr(builder, "_load", lambda name: None)
    알림: list[dict] = []

    async def on_route(상태):
        알림.append(dict(상태))

    await builder.run_query({"base_product_id": "p1", "basis": "SELF"}, on_route=on_route)
    assert 알림[0]["scenario"] == "S1_EVALUATE"
    assert 알림[0]["query_spec"]["base_product_ref"] == "p1"


@pytest.mark.asyncio
async def test_화면에서_고른_추천_기준이_문장에서_읽은_기준을_이긴다(monkeypatch):
    """'엄마 선물'이라고 써도 내 기준 탭이면 내 기준으로 찾는다."""
    async def normalize(state):
        return {"query_spec": {"category": "base", "target": "OTHER"}}

    monkeypatch.setattr(
        builder, "_load", lambda name: normalize if name == "normalize" else None
    )
    알림: list[str] = []

    async def on_route(상태):
        알림.append(상태["query_spec"]["target"])

    결과 = await builder.run_query(
        {"raw_query": "엄마 선물 쿠션", "basis": "SELF"}, on_route=on_route
    )
    assert 알림 == ["SELF"]
    assert 결과["query_spec"]["target"] == "SELF"


@pytest.mark.asyncio
async def test_경로_알림이_실패하면_실패를_알리고_올린다(monkeypatch):
    monkeypatch.setattr(builder, "_load", lambda name: None)
    받은: list[Exception] = []

    async def on_route(상태):
        raise RuntimeError("기록 실패")

    async def on_fail(e):
        받은.append(e)

    with pytest.raises(RuntimeError):
        await builder.run_query({"raw_query": "쿠션"}, on_route=on_route, on_fail=on_fail)
    assert len(받은) == 1
