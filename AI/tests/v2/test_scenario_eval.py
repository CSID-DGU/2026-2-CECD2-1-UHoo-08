"""시나리오 평가 러너가 지켜야 할 성질.

실제 경로는 키와 DB 가 있어야 돌므로 여기서는 돌리지 않는다. 레코드를 처음 상태로
바꾸는 일과, 판정을 모아 리포트로 쓰는 일만 본다.
"""
import json

import pytest

from eval import run_scenario_eval as 러너


def _레코드(id_, scenario="S2_SEARCH", split="test", **입력):
    return {
        "id": id_, "split": split, "source": "claude", "tags": ["conflict"],
        "input": {"persona_id": "persona-0001", "scenario": scenario, **입력},
        "expected": {"must_exclude": ["o1"], "non_empty": ["items"]},
        "check": "property",
    }


def test_레코드를_처음_상태로_바꾼다():
    상태 = 러너.initial_state(
        _레코드("scenario-g-0001", raw_query="여름 쿠션",
                query_spec={"category": "base", "target": "POPULAR"}),
        "user-1",
    )
    assert 상태 == {
        "job_id": "eval-scenario-g-0001", "user_id": "user-1", "scenario": "S2_SEARCH",
        "raw_query": "여름 쿠션",
        "query_spec": {"category": "base", "target": "POPULAR", "request_type": "SEARCH"},
        "basis": "POPULAR", "target_profile": None, "trace": [],
    }


def test_화면_기준이_질의_해석의_기준을_이긴다():
    상태 = 러너.initial_state(
        _레코드("scenario-g-0002", basis="OTHER", target_profile={"skinType": "DRY"},
                query_spec={"target": "SELF"}),
        "user-1",
    )
    assert 상태["basis"] == "OTHER" and 상태["query_spec"]["target"] == "OTHER"
    assert 상태["target_profile"] == {"skinType": "DRY"}


def test_상품_평가는_기준_상품을_두_자리에_둔다():
    상태 = 러너.initial_state(_레코드("scenario-g-0003", scenario="S1_EVALUATE",
                                      base_product_id="b1"), "user-1")
    assert 상태["base_product_id"] == "b1"
    assert 상태["query_spec"]["request_type"] == "EVALUATE"
    assert 상태["query_spec"]["base_product_ref"] == "b1"


def _카드(pid):
    return {"productId": pid, "price": 1000, "totalScore": 80, "breakdown": [], "badges": []}


@pytest.mark.asyncio
async def test_성질별_시나리오별로_모으고_실패와_오류를_남긴다():
    결과들 = {
        "scenario-g-0001": {"items": [_카드("p1")]},              # 모두 통과
        "scenario-g-0002": {"items": [_카드("o1")]},              # must_exclude 실패
    }

    async def 한_건(rec):
        if rec["id"] == "scenario-g-0003":
            raise RuntimeError("DB 끊김")
        return 결과들[rec["id"]], {}

    기록 = [_레코드("scenario-g-0001"), _레코드("scenario-g-0002"),
            _레코드("scenario-g-0003", scenario="S1_EVALUATE")]
    결과 = await 러너.evaluate(기록, 한_건)

    assert 결과["총건수"] == 3
    assert 결과["성질"] == {"must_exclude": (1, 2), "non_empty": (2, 2)}
    assert 결과["경로"] == {"S2_SEARCH": (1, 2), "S1_EVALUATE": (0, 1)}
    assert [s["id"] for s in 결과["실패"]] == ["scenario-g-0002", "scenario-g-0003"]
    assert "o1" in 결과["실패"][0]["틀린_성질"]["must_exclude"]
    assert "DB 끊김" in 결과["실패"][1]["error"]


@pytest.mark.asyncio
async def test_판정이_터져도_그_레코드만_오류로_남기고_나머지를_잰다():
    """등록된 키라도 값 모양이 틀리면 판정 함수 안에서 터진다."""
    망가진 = _레코드("scenario-g-0001")
    망가진["expected"] = {"must_exclude_reason": []}

    async def 한_건(rec):
        return {"items": [_카드("p1")]}, {}

    결과 = await 러너.evaluate([망가진, _레코드("scenario-g-0002")], 한_건)

    assert 결과["성질"] == {"must_exclude": (1, 1), "non_empty": (1, 1)}
    assert 결과["경로"] == {"S2_SEARCH": (1, 2)}
    assert [s["id"] for s in 결과["실패"]] == ["scenario-g-0001"]
    assert 결과["실패"][0]["stage"] == "판정"
    assert "AttributeError" in 결과["실패"][0]["error"]
    assert "판정 중 오류" in 러너.to_markdown(결과, "test", [])


def test_리포트는_양식의_네_항목을_갖는다():
    결과 = {
        "총건수": 2,
        "성질": {"must_exclude": (1, 2)},
        "경로": {"S2_SEARCH": (1, 2)},
        "실패": [{"id": "scenario-g-0002", "scenario": "S2_SEARCH", "tags": ["conflict"],
                  "query": "여름 쿠션", "틀린_성질": {"must_exclude": "결과에 남아 있다: ['o1']"}}],
    }
    본문 = 러너.to_markdown(결과, "test", ["s2_search_v1.jsonl"])
    for 제목 in ("## 1. 데이터", "## 2. 핵심 지표", "## 3. 실패 사례 (1건)", "## 4. 다음 조치"):
        assert 제목 in 본문
    assert "| `S2_SEARCH` | 1 / 2 | 50.0% |" in 본문
    assert "`s2_search_v1.jsonl`" in 본문
    assert "scenario-g-0002" in 본문 and "결과에 남아 있다" in 본문


def test_골든셋을_split과_id로_고른다(tmp_path, monkeypatch):
    monkeypatch.setattr(러너, "GOLDEN_DIR", tmp_path)
    (tmp_path / "s2_search_v1.jsonl").write_text("\n".join(json.dumps(r) for r in [
        _레코드("scenario-g-0001", split="dev"), _레코드("scenario-g-0002"),
        _레코드("scenario-g-0003"),
    ]) + "\n", encoding="utf-8")

    기록, 파일들 = 러너.read_golden("test")
    assert [r["id"] for r in 기록] == ["scenario-g-0002", "scenario-g-0003"]
    assert 파일들 == ["s2_search_v1.jsonl"]
    assert [r["id"] for r in 러너.read_golden(None, "scenario-g-0001")[0]] == ["scenario-g-0001"]


def _수정_레코드():
    return {
        "id": "scenario-g-0081", "split": "dev", "source": "claude",
        "input": {"persona_id": "persona-0001", "scenario": "S7_REFINE",
                  "raw_query": "더 저렴한 제품으로", "refine_presets": ["CHEAPER"],
                  "parent": {"raw_query": "4만원 이하 쿠션",
                             "query_spec": {"request_type": "SEARCH", "category": "base",
                                            "budget": {"max": 40000}}}},
        "expected": {"change_present": True}, "check": "property",
    }


def test_조건_수정은_이전_검색을_레코드로_만들고_이전_job을_가리킨다():
    rec = _수정_레코드()
    상태 = 러너.initial_state(rec, "user-1")
    assert 상태["parent_job_id"] == "eval-scenario-g-0081-parent"
    assert 상태["query_spec"]["request_type"] == "REFINE"

    이전 = 러너.parent_record(rec)
    assert 이전["input"]["scenario"] == "S2_SEARCH"
    assert 이전["input"]["query_spec"]["budget"] == {"max": 40000}
    assert 러너.initial_state(이전, "user-1")["job_id"] == "eval-scenario-g-0081-parent"


def test_이전_job과_이번_job을_메모리에_둔다():
    rec = _수정_레코드()
    이전_상태 = {"scenario": "S2_SEARCH", "query_spec": {"request_type": "SEARCH"},
                 "result": {"items": [{"productId": "p1"}]},
                 "candidates": [{"product_id": "p1", "source": "retrieve", "similarity": 0.9}]}
    job들 = 러너.memory_jobs(rec, 이전_상태)

    이전 = job들["eval-scenario-g-0081-parent"]
    assert 이전["scenario"] == "S2_SEARCH" and 이전["result"]["items"][0]["productId"] == "p1"
    assert 이전["state_snapshot"]["candidates"][0]["product_id"] == "p1"
    assert job들["eval-scenario-g-0081"]["refine_presets"] == ["CHEAPER"]


@pytest.mark.asyncio
async def test_조건_수정을_도는_동안만_job을_메모리에서_읽는다():
    from services import job_store

    원래 = job_store.load_job
    with 러너._메모리에서_job_읽기({"j1": {"id": "j1"}}):
        assert await job_store.load_job("j1", columns="id") == {"id": "j1"}
        assert await job_store.load_job("없음") is None
    assert job_store.load_job is 원래


# 홈 환경

def test_홈_환경은_홈_실행과_같은_질의_해석으로_시작한다():
    상태 = 러너.initial_state(
        _레코드("scenario-g-0121", "HOME_ENV", env_summary={"needs": []}), "u1",
    )
    assert 상태["scenario"] == "HOME_ENV" and 상태["raw_query"] == ""
    assert 상태["query_spec"]["request_type"] == "SEARCH"
    assert 상태["query_spec"]["use_env"] is True and 상태["query_spec"]["target"] == "SELF"


@pytest.mark.asyncio
async def test_홈_환경을_도는_동안만_환경_집계를_레코드의_값으로_바꾼다(monkeypatch):
    import importlib
    import sys

    # 환경 집계(B)가 들어온 뒤에도 원래 단계로 되돌리는지 본다
    async def 원래_단계(state):
        return {"env_summary": None}

    원래 = type(sys)("graph.nodes.env_history")
    원래.env_history = 원래_단계
    monkeypatch.setitem(sys.modules, "graph.nodes.env_history", 원래)

    요약 = {"region": "서울", "needs": [{"key": "UV_PROTECT"}]}
    with 러너._환경_고정(요약):
        단계 = importlib.import_module("graph.nodes.env_history").env_history
        assert await 단계({}) == {"env_summary": 요약}
    assert sys.modules["graph.nodes.env_history"] is 원래


def test_환경_집계가_없으면_바꾼_단계를_치운다(monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "graph.nodes.env_history", raising=False)
    with 러너._환경_고정({"needs": []}):
        assert "graph.nodes.env_history" in sys.modules
    assert "graph.nodes.env_history" not in sys.modules


# 홈 루틴

def _보유행(upid, pid, name):
    return {"user_product_id": upid, "product_id": pid, "name": name}


def test_상품_id_로_적은_궁합_쌍을_보유_제품_행으로_옮긴다():
    보유 = [_보유행("u1", "p1", "레티놀"), _보유행("u2", "p2", "비타민C"), _보유행("u3", "p3", "크림")]
    점검 = 러너.routine_check_from(
        [{"a": "p1", "b": "p2", "level": "AVOID"}, {"a": "p2", "b": "p3", "level": "OK"}], 보유,
    )
    assert 점검["pairs"][0]["a"] == {"user_product_id": "u1", "name": "레티놀"}
    assert 점검["pairs"][0]["b"]["user_product_id"] == "u2" and 점검["pairs"][0]["level"] == "AVOID"
    assert 점검["counts"] == {"ok": 1, "separate": 0, "avoid": 1}
    assert 점검["checked_user_product_ids"] == ["u1", "u2", "u3"]
    from contracts.result import CompatibilityPair, RoutineCounts
    RoutineCounts.model_validate(점검["counts"])
    [CompatibilityPair.model_validate(쌍) for 쌍 in 점검["pairs"]]


def test_보유_제품이_없거나_쌍의_상품이_보유에_없으면_멈춘다():
    with pytest.raises(RuntimeError, match="보유 제품이 없어"):
        러너.routine_check_from([{"a": "p1", "b": "p2", "level": "AVOID"}], [])
    with pytest.raises(RuntimeError, match="p9"):
        러너.routine_check_from([{"a": "p1", "b": "p9", "level": "AVOID"}], [_보유행("u1", "p1", "a")])


@pytest.mark.asyncio
async def test_홈_루틴을_도는_동안만_루틴_점검을_바꾼다(monkeypatch):
    import importlib
    import sys

    monkeypatch.delitem(sys.modules, "graph.nodes.compatibility", raising=False)
    with 러너._루틴_고정([{"a": "p1", "b": "p2", "level": "AVOID"}]):
        단계 = importlib.import_module("graph.nodes.compatibility").compatibility
        나옴 = await 단계({"inventory": [_보유행("u1", "p1", "a"), _보유행("u2", "p2", "b")]})
        assert 나옴["routine_check"]["counts"]["avoid"] == 1
    assert "graph.nodes.compatibility" not in sys.modules


@pytest.mark.asyncio
async def test_판정_자료는_보유_상품과_성분_부품이_없을_때의_AVOID_상대를_담는다(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "services.ingredient_store", None)
    상태 = {"inventory": [_보유행("u1", "p1", "a"), _보유행("u2", "p2", "b")],
            "replace_target": {"user_product_id": "u1"},
            "result": {"replacement": {"items": [{"productId": "n1"}]}}}
    자료 = await 러너.routine_context(상태)
    assert 자료 == {"product_of": {"u1": "p1", "u2": "p2"}, "avoid_with": None}


@pytest.mark.asyncio
async def test_성분_부품이_있으면_바꿀_제품을_뺀_보유_제품과_다시_판정한다(monkeypatch):
    import sys
    import types

    받은: list = []

    async def load_product_ingredients(ids):
        return {pid: ["레티놀"] for pid in ids}

    async def load_rules():
        return []

    def check_compatibility(inventory, product, rules):
        받은.append([항목["user_product_id"] for 항목 in inventory])
        return [{"user_product_id": "u2", "level": "AVOID"}] if product["product_id"] == "n1" else []

    monkeypatch.setitem(sys.modules, "services.ingredient_store", types.SimpleNamespace(
        load_product_ingredients=load_product_ingredients, load_rules=load_rules))
    monkeypatch.setitem(sys.modules, "rules.compatibility",
                        types.SimpleNamespace(check_compatibility=check_compatibility))
    상태 = {"inventory": [_보유행("u1", "p1", "a"), _보유행("u2", "p2", "b")],
            "replace_target": {"user_product_id": "u1"},
            "product_meta": {"n1": {}, "n2": {}},
            "result": {"replacement": {"items": [{"productId": "n1"}, {"productId": "n2"}]}}}
    자료 = await 러너.routine_context(상태)
    assert 자료["avoid_with"] == {"n1": ["u2"], "n2": []}
    assert 받은 == [["u2"], ["u2"]]
