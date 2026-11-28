"""캡션 키워드 추출 — 사전 표기 · 제외어 · 헤어 줄 · 짧은 영문 · @멘션."""
from rules.keyword_extract import CONCERN, INGREDIENT, extract_keywords, load_keywords

D = load_keywords()


def ids(caption):
    return [h.keyword_id for h in extract_keywords(caption, D)]


def test_dictionary_loads_with_both_groups():
    groups = {k.group for k in D.keywords}
    assert groups == {INGREDIENT, CONCERN}
    assert "pdrn" in D.by_id and "hydration" in D.by_id


def test_finds_ingredient_and_concern_once_each():
    cap = "VT PDRN 에센스 너무 좋아요\n수분 가득, 촉촉해요\n#pdrn #수분크림"
    assert ids(cap) == ["pdrn", "hydration"]


def test_hit_carries_evidence():
    h = extract_keywords("요즘 판테놀 크림만 써요", D)[0]
    assert (h.keyword_id, h.group, h.form) == ("panthenol", INGREDIENT, "판테놀")
    assert "판테놀" in h.line


def test_evidence_contains_match_even_in_long_line():
    cap = "가" * 300 + " 판테놀 크림 " + "나" * 300
    h = extract_keywords(cap, D)[0]
    assert h.form == "판테놀" and "판테놀" in h.line
    assert len(h.line) <= len("판테놀") + 2 * 60


def test_evidence_points_past_excluded_word():
    # 제외어(시카고)를 지워도 위치가 어긋나지 않아, 멀리 있는 진짜 표기 구간을 근거로 남긴다
    h = extract_keywords("시카고 여행 " + "가" * 200 + " 시카 크림", D)[0]
    assert h.keyword_id == "cica" and h.line.endswith("시카 크림") and "시카고" not in h.line


def test_aliases_map_to_one_keyword():
    assert ids("병풀 추출물 진짜 순해요") == ["cica"]
    assert ids("센텔라 앰플") == ["cica"]


def test_exclude_word_is_not_keyword():
    assert ids("시카고 여행 브이로그") == []


def test_hair_and_body_lines_are_skipped():
    assert ids("팬틴 판테놀 캡슐 트리트먼트") == []
    assert ids("엑소좀 바이오 스칼프 앰플 증정\n판테놀 크림 추천") == ["panthenol"]


def test_english_skip_words_match_whole_words_only():
    assert ids("Everybody loves this panthenol cream") == ["panthenol"]
    assert ids("panthenol body lotion") == []


def test_short_ascii_needs_word_boundary():
    assert ids("bha 토너로 각질 정리") == ["acids", "exfoliation"]
    assert ids("alpha 버전 출시") == []


def test_account_mentions_are_ignored():
    assert ids("@cica_official 감사합니다") == []


def test_empty_caption():
    assert ids(None) == [] and ids("") == []
