"""피드백 반영 평가가 지켜야 할 성질.

세션을 가중치로 바꾸는 계산이 실제 반영과 다르면, 평가가 실제와 다른 가중치를 재게 된다.
실제 경로는 키와 DB 가 있어야 돌므로 여기서는 돌리지 않는다.
"""
import json

import pytest

from eval import feedback_checks as 판정
from eval import run_feedback_eval as 러너
from eval import run_scenario_eval, validate
from rules.score_weights import DEFAULT_WEIGHTS


def _카드(pid, price):
    return {"productId": pid, "price": price, "totalScore": 80, "breakdown": [], "badges": []}


def _결과(*카드):
    return {"items": list(카드)}


# 판정

def test_저렴한_상품의_평균_순위가_오르면_통과다():
    기본 = _결과(_카드("비쌈", 40000), _카드("중간", 30000), _카드("쌈", 10000), _카드("더쌈", 9000))
    바뀐 = _결과(_카드("쌈", 10000), _카드("더쌈", 9000), _카드("비쌈", 40000), _카드("중간", 30000))
    assert 판정.cheaper_rank_up(True, 기본, 바뀐)[0]
    통과, 설명 = 판정.cheaper_rank_up(True, 기본, 기본)
    assert not 통과 and "평균 순위" in 설명


def test_결과에서_빠진_저렴한_상품은_내려간_것으로_본다():
    기본 = _결과(_카드("비쌈", 40000), _카드("쌈", 10000))
    바뀐 = _결과(_카드("비쌈", 40000), _카드("새", 20000))
    assert not 판정.cheaper_rank_up(True, 기본, 바뀐)[0]


def test_결과가_짧아져_빠진_저렴한_상품은_오른_것으로_보지_않는다():
    """결과마다 마지막 다음 순위를 따로 두면 빠진 상품이 3.5위에서 2위로 오른 것처럼 보인다."""
    기본 = _결과(_카드("고가A", 40000), _카드("고가B", 30000),
                _카드("저가C", 10000), _카드("저가D", 9000))
    바뀐 = _결과(_카드("고가A", 40000))
    통과, 설명 = 판정.cheaper_rank_up(True, 기본, 바뀐)
    assert not 통과 and "3.50 → 5.00" in 설명


def test_가격을_아는_카드가_적으면_판정할_수_없다():
    assert not 판정.cheaper_rank_up(True, _결과(_카드("a", 1000)), _결과())[0]


def test_되돌린_뒤_순서가_같아야_한다():
    기본 = _결과(_카드("a", 1), _카드("b", 2))
    assert 판정.revert_restores(True, 기본, _결과(_카드("a", 1), _카드("b", 2)))[0]
    assert not 판정.revert_restores(True, 기본, _결과(_카드("b", 2), _카드("a", 1)))[0]
    # 둘 다 비었으면 같다고 보지 않는다
    assert not 판정.revert_restores(True, _결과(), _결과())[0]


def test_모르는_성질은_실패다():
    나옴 = 판정.judge({"모름": True}, _결과(), _결과())
    assert 나옴["모름"][0] is False


# 세션 → 가중치

def test_세션의_피드백을_실제_반영과_같은_합산으로_바꾼다():
    세션 = {"events": [{"reasons": ["TOO_EXPENSIVE"]}] * 3}
    가중치 = 러너.session_weights(세션)
    assert 가중치["budget_fit"] == pytest.approx(DEFAULT_WEIGHTS["budget_fit"] + 0.15)
    assert 가중치["review"] == DEFAULT_WEIGHTS["review"]


def test_되돌린_피드백은_빠지고_모두_되돌리면_기본_가중치다():
    세션 = {"events": [{"reasons": ["TOO_EXPENSIVE"]}, {"reasons": ["BAD_REVIEWS"]}, {"revert": 0}]}
    변경들 = 러너.session_changes(세션)
    assert [변경["reverted"] for 변경 in 변경들] == [True, False]
    가중치 = 러너.session_weights(세션)
    assert 가중치["budget_fit"] == DEFAULT_WEIGHTS["budget_fit"]
    assert 가중치["review"] == pytest.approx(DEFAULT_WEIGHTS["review"] + 0.05)

    모두 = {"events": [{"reasons": ["TOO_EXPENSIVE"]}, {"revert": 0}]}
    assert 러너.session_weights(모두) == DEFAULT_WEIGHTS


def test_점수로_옮길_수_없는_이유는_변경을_만들지_않는다():
    assert 러너.session_changes({"events": [{"reasons": ["ALREADY_HAVE_SIMILAR"]}]}) == []


# 러너

def _레코드(id_, split="test", **기대):
    return {"id": id_, "split": split, "source": "claude", "tags": ["cheaper"],
            "input": {"session_id": "feedback-0001", "persona_id": "persona-0001",
                      "scenario": "S2_SEARCH", "raw_query": "쿠션",
                      "query_spec": {"category": "base"}},
            "expected": 기대 or {"cheaper_rank_up": True}, "check": "property"}


@pytest.mark.asyncio
async def test_기본과_바뀐_가중치로_돌려_성질별로_모은다():
    받은: list = []
    기본 = _결과(_카드("비쌈", 40000), _카드("쌈", 10000))
    바뀐 = _결과(_카드("쌈", 10000), _카드("비쌈", 40000))

    async def 한_쌍(rec, 가중치):
        받은.append(가중치["budget_fit"])
        if rec["id"] == "scenario-g-0103":
            raise RuntimeError("DB 끊김")
        return (기본, 바뀐) if rec["id"] == "scenario-g-0101" else (기본, 기본)

    세션들 = {"feedback-0001": {"id": "feedback-0001", "events": [{"reasons": ["TOO_EXPENSIVE"]}]}}
    결과 = await 러너.evaluate(
        [_레코드("scenario-g-0101"), _레코드("scenario-g-0102"), _레코드("scenario-g-0103")],
        세션들, 한_쌍,
    )
    assert 받은 == [pytest.approx(0.30)] * 3
    assert 결과["성질"] == {"cheaper_rank_up": (1, 2)}
    assert [s["id"] for s in 결과["실패"]] == ["scenario-g-0102", "scenario-g-0103"]
    assert "DB 끊김" in 결과["실패"][1]["error"]

    본문 = 러너.to_markdown(결과, "test", ["feedback_v1.jsonl"])
    for 제목 in ("# 피드백 반영", "## 1. 데이터", "## 2. 핵심 지표", "## 3. 실패 사례 (2건)",
                 "## 4. 다음 조치"):
        assert 제목 in 본문
    assert "| `cheaper_rank_up` | 1 / 2 | 50.0% |" in 본문


@pytest.mark.asyncio
async def test_없는_세션은_그_레코드만_오류로_남긴다():
    async def 한_쌍(rec, 가중치):
        raise AssertionError("부르면 안 된다")

    결과 = await 러너.evaluate([_레코드("scenario-g-0101")], {}, 한_쌍)
    assert 결과["실패"][0]["session"] == "feedback-0001" and "error" in 결과["실패"][0]


def _쓰기(경로, 레코드들):
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in 레코드들),
                    encoding="utf-8")


def test_피드백_골든셋은_피드백_러너만_읽는다(tmp_path, monkeypatch):
    monkeypatch.setattr(러너, "GOLDEN_DIR", tmp_path)
    monkeypatch.setattr(run_scenario_eval, "GOLDEN_DIR", tmp_path)
    _쓰기(tmp_path / "feedback_v1.jsonl", [_레코드("scenario-g-0101"), _레코드("scenario-g-0102", "dev")])
    _쓰기(tmp_path / "s2_search_v1.jsonl", [_레코드("scenario-g-0001")])

    기록, 파일들 = 러너.read_golden("test")
    assert [r["id"] for r in 기록] == ["scenario-g-0101"] and 파일들 == ["feedback_v1.jsonl"]
    assert [r["id"] for r in run_scenario_eval.read_golden(None)[0]] == ["scenario-g-0001"]


def test_검증은_피드백_골든셋에_피드백_성질만_허락한다(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "AI_ROOT", tmp_path)
    _쓰기(tmp_path / "eval/golden/scenario/feedback_v1.jsonl", [
        _레코드("scenario-g-0101", revert_restores=True),
        _레코드("scenario-g-0102", must_exclude=[]),
    ])
    문제, _ = validate.collect((tmp_path / "data/synthetic", tmp_path / "eval/golden"))
    assert len(문제) == 1 and ":2:" in 문제[0] and "must_exclude" in 문제[0]
