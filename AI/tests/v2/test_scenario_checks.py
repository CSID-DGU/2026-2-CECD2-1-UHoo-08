"""시나리오 성질 판정이 지켜야 할 성질.

판정이 틀리면 리포트 수치가 틀린다. 통과해야 할 결과와 실패해야 할 결과를 하나씩 본다.
"""
import json

import pytest

from eval import scenario_checks as 판정
from eval import validate


def _카드(pid, price=20000, breakdown=(), badges=()):
    return {"productId": pid, "price": price, "totalScore": 80,
            "breakdown": [{"key": k, "label": k, "score": 80, "weight": 0.5} for k in breakdown],
            "badges": [{"type": t, "text": "x"} for t in badges]}


def _결과(items=(), **값):
    return {"items": list(items), "alternatives": [], "similarUserProducts": [],
            "excluded": [], **값}


_메타 = {
    "p1": {"category": "base", "feature_json": {"product_type": "쿠션"}},
    "p2": {"category": "base", "feature_json": {"product_type": "파운데이션"}},
    "p3": {"category": "sun", "feature_json": {}},
}


def test_빠져야_할_상품():
    assert 판정.must_exclude(["o1"], _결과([_카드("p1")]), _메타)[0]
    통과, 설명 = 판정.must_exclude(["o1", "p1"], _결과([_카드("p1")]), _메타)
    assert not 통과 and "p1" in 설명


def test_제외_사유():
    결과 = _결과(excluded=[{"productId": "o1", "reason": "OWNED"},
                            {"productId": "c1", "reason": "CONFLICT"}])
    assert 판정.must_exclude_reason({"o1": "OWNED", "c1": "CONFLICT"}, 결과, _메타)[0]
    assert not 판정.must_exclude_reason({"c1": "OWNED"}, 결과, _메타)[0]
    assert not 판정.must_exclude_reason({"x1": "OWNED"}, 결과, _메타)[0]


def test_상위_5개_조건():
    결과 = _결과([_카드("p1", 20000), _카드("p2", 28000)])
    assert 판정.top5_all({"category": "base", "price_max": 30000}, 결과, _메타)[0]
    assert not 판정.top5_all({"price_max": 25000}, 결과, _메타)[0]
    assert not 판정.top5_all({"product_type": "쿠션"}, 결과, _메타)[0]
    assert not 판정.top5_all({"category": "base"}, _결과([_카드("p3")]), _메타)[0]
    # 가격을 모르면 상한을 지켰다고 볼 수 없다
    assert not 판정.top5_all({"price_max": 30000}, _결과([_카드("p1", None)]), _메타)[0]


def test_상위_5개만_본다():
    결과 = _결과([_카드("p1")] * 5 + [_카드("p3")])
    assert 판정.top5_all({"category": "base"}, 결과, _메타)[0]


def test_결과가_비면_상위_조건과_점수_항목은_실패다():
    assert not 판정.top5_all({"category": "base"}, _결과(), _메타)[0]
    assert not 판정.breakdown_has(["review"], _결과(), _메타)[0]
    assert not 판정.breakdown_lacks(["review"], _결과(), _메타)[0]


def test_점수_항목_유무는_상위_1개로_본다():
    결과 = _결과([_카드("p1", breakdown=["popularity", "review"]), _카드("p2", breakdown=["personalization"])])
    assert 판정.breakdown_has(["popularity"], 결과, _메타)[0]
    assert not 판정.breakdown_has(["env_fit"], 결과, _메타)[0]
    assert 판정.breakdown_lacks(["personalization"], 결과, _메타)[0]
    assert not 판정.breakdown_lacks(["review"], 결과, _메타)[0]


def test_배지는_상위_5개_중_하나에_있으면_된다():
    결과 = _결과([_카드("p1"), _카드("p2", badges=["ENV"])])
    assert 판정.badge_any(["ENV"], 결과, _메타)[0]
    assert 판정.badge_any(["VALUE", "ENV"], 결과, _메타)[0]
    assert not 판정.badge_any(["TREND"], 결과, _메타)[0]
    여섯째만 = _결과([_카드("p1")] * 5 + [_카드("p2", badges=["ENV"])])
    assert not 판정.badge_any(["ENV"], 여섯째만, _메타)[0]


def test_비어_있지_않은_필드는_snake_case로_적어도_된다():
    결과 = _결과([_카드("p1")], similarUserProducts=[_카드("c1")])
    assert 판정.non_empty(["items", "similar_user_products"], 결과, _메타)[0]
    assert not 판정.non_empty(["alternatives"], 결과, _메타)[0]


def test_대체_후보_점수_하한():
    대체 = [{"productId": "a1", "totalScore": 72}, {"productId": "a2", "totalScore": 45}]
    assert 판정.alternatives_min_score(40, _결과(alternatives=대체), _메타)[0]
    통과, 설명 = 판정.alternatives_min_score(50, _결과(alternatives=대체), _메타)
    assert not 통과 and "a2" in 설명


def test_기대_성질을_모두_판정하고_모르는_성질은_실패다():
    결과 = _결과([_카드("p1", breakdown=["review"])])
    나옴 = 판정.judge({"must_exclude": ["o1"], "breakdown_has": ["review"], "모름": 1}, 결과, _메타)
    assert {k: v[0] for k, v in 나옴.items()} == {
        "must_exclude": True, "breakdown_has": True, "모름": False}


# 데이터 검증

def _쓰기(경로, 레코드들):
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in 레코드들) + "\n",
                    encoding="utf-8")


@pytest.fixture
def 가짜루트(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "AI_ROOT", tmp_path)
    return tmp_path


def _골든(**기대):
    return {"id": "scenario-g-0001", "split": "dev", "source": "claude",
            "input": {"persona_id": "persona-0001", "scenario": "S2_SEARCH"},
            "expected": 기대, "check": "property"}


def test_시나리오_골든셋의_모르는_성질을_잡는다(가짜루트):
    _쓰기(가짜루트 / "eval/golden/scenario/s2_search_v1.jsonl",
          [_골든(must_exclude=[], top10_all={"category": "base"})])
    문제, _ = validate.collect((가짜루트 / "data/synthetic", 가짜루트 / "eval/golden"))
    assert len(문제) == 1 and "top10_all" in 문제[0]


def test_아는_성질만_쓰면_통과하고_상품_id를_모은다(가짜루트):
    보유 = "11111111-1111-1111-1111-111111111111"
    충돌 = "22222222-2222-2222-2222-222222222222"
    기준 = "33333333-3333-3333-3333-333333333333"
    레코드 = _골든(must_exclude=[보유], must_exclude_reason={충돌: "CONFLICT"},
                  top5_all={"category": "base"})
    레코드["input"]["base_product_id"] = 기준
    _쓰기(가짜루트 / "eval/golden/scenario/s1_evaluate_v1.jsonl", [레코드])
    문제, 상품 = validate.collect((가짜루트 / "data/synthetic", 가짜루트 / "eval/golden"))
    assert 문제 == []
    assert 상품 == {보유, 충돌, 기준}
