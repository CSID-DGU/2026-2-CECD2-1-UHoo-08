"""검수 문서 → 제품 매칭 골든셋 변환."""
from scripts.build_match_golden import build_record, load_labels

NAMES = {"에스네이처 딥 아쿠아 스쿠알란 베리어 세럼 50ml": "pid-serum"}
POST = {"id": 7, "username": "u", "caption": "캡션"}


def test_마스터_이름은_ID로_아니면_미등록으로():
    r = build_record(POST, {"products": ["에스네이처 딥 아쿠아 스쿠알란 베리어 세럼 50ml", "장벽크림토너"]}, NAMES)
    assert r["expected"] == {"product_ids": ["pid-serum"], "unregistered": ["장벽크림토너"], "none": False}
    assert r["id"] == "trend-g-1007" and r["split"] == "test" and r["check"] == "exact"


def test_ok_판정만_정답에_넣는다():
    r = build_record(POST, {"products": [], "verdicts": {"a": "ok", "b": "bad", "c": "ok"}}, NAMES)
    assert r["expected"]["product_ids"] == ["a", "c"]


def test_제품_없음이면_다른_입력은_무시한다():
    r = build_record(POST, {"none": True, "products": ["x"], "verdicts": {"a": "ok"}}, NAMES)
    assert r["expected"] == {"product_ids": [], "unregistered": [], "none": True}


def test_빈_문서는_검수하지_않은_것이라_뺀다(tmp_path):
    (tmp_path / "1.json").write_text('{"none": false, "products": [], "verdicts": {}}', encoding="utf-8")
    (tmp_path / "2.json").write_text('{"none": true, "products": [], "verdicts": {}}', encoding="utf-8")
    assert list(load_labels(tmp_path)) == [2]
