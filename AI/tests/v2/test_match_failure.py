"""실패 단계 분류와 지표 (rules/match_failure)."""
from rules.match_failure import Row, classify_item, evaluate


def row(status="unmatched", pid=None, method=None, cands=(), pool=(), choice=None, mt="product"):
    return Row(mt, status, pid, method, list(cands), list(pool), choice)


def test_추출_언급이_없으면_extract_miss():
    assert classify_item("a", [], [row()]) == "extract_miss"


def test_브랜드만으로_뽑았으면_extract_misclass():
    assert classify_item("a", [0], [row(mt="brand_only")]) == "extract_misclass"


def test_후보에_없으면_retrieval_miss_이고_K에_따라_달라진다():
    r = [row(cands=["x", "y", "a"])]
    assert classify_item("a", [0], r, k=2) == "retrieval_miss"
    assert classify_item("a", [0], r, k=5) != "retrieval_miss"


def test_후보에는_있지만_판정_후보에서_빠지면_pool_cut():
    assert classify_item("a", [0], [row(cands=["x", "a"], pool=["x"], choice="x", method="llm")]) == "pool_cut"


def test_규칙이_다른_제품으로_확정하면_rule_wrong():
    assert classify_item("a", [0], [row("matched", "x", "rule", cands=["x", "a"])]) == "rule_wrong"


def test_LLM이_정답을_고르고_규칙이_막으면_accept_blocked():
    assert classify_item("a", [0], [row("review", None, "llm", ["a"], ["a"], "a")]) == "accept_blocked"


def test_LLM이_다른_답을_내면_llm_wrong():
    assert classify_item("a", [0], [row("unmatched", None, "llm", ["a"], ["a"], "unmatched")]) == "llm_wrong"


def test_여러_언급이면_가장_멀리_간_것으로_본다():
    rows = [row(cands=["x"]), row("matched", "a", "hashtag", ["a"])]
    assert classify_item("a", [0, 1], rows) == "matched"


def gold(post_id, items):
    return {"input": {"post_id": post_id}, "expected": {"items": items}}


def test_지표는_검수된_항목만으로_계산하고_당시_마스터를_재현한다():
    golds = [
        gold(1, [{"kind": "in_db", "product_id": "a", "mentions": [0]},
                 {"kind": "not_in_db", "brand": "B", "name": "n", "mentions": [1]}]),
        gold(2, [{"kind": "in_db", "product_id": "new", "mentions": [0]}]),
        gold(3, []),
    ]
    rows = {
        1: [row("matched", "a", "rule", ["a"]), row("matched", "z", "llm", ["z"], ["z"], "z")],
        2: [row("matched", "new", "rule", ["new"])],
        3: [row("matched", "q", "llm", ["q"], ["q"], "q")],
    }
    out = evaluate(golds, rows)
    assert out["stages"]["matched"] == 2 and out["recall_in_db"]["rate"] == 1.0
    assert out["auto_precision"] == {"hit": 2, "total": 2, "rate": 1.0}
    assert out["precision"]["hit"] == 2 and out["precision"]["total"] == 4      # z · q 는 오탐
    assert out["match_rate_all"]["total"] == 3
    old = evaluate(golds, rows, master_ids={"a", "z", "q"})
    assert old["items"]["not_in_db"] == 2 and old["stages"]["matched"] == 1
