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
