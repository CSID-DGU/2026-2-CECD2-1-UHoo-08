"""성분 정규화가 지켜야 할 성질.

표기가 달라도 같은 성분이면 같은 키로 묶여야 하고, 모르는 성분은 버리지
않아야 한다(모르는 것과 없는 것은 다르다).
"""
from rules.ingredient_normalize import normalize_key, resolve_canonical


def test_공백_하이픈_가운뎃점을_없앤다():
    assert normalize_key("나이아신 아마이드") == normalize_key("나이아신아마이드")
    assert normalize_key("Tea-Tree") == normalize_key("Tea Tree")
    assert normalize_key("비타민·B3") == normalize_key("비타민B3")


def test_대소문자를_가리지_않는다():
    assert normalize_key("Niacinamide") == normalize_key("niacinamide")


def test_사전에_있으면_표준명으로_바뀐다():
    alias_map = {normalize_key("니아신아마이드"): "나이아신아마이드"}
    assert resolve_canonical(["니아신아마이드"], alias_map) == ["나이아신아마이드"]


def test_사전에_없으면_원문을_그대로_쓴다():
    """조용히 빼면 PreFilter·Compatibility가 성분이 없는 것으로 오판한다."""
    assert resolve_canonical(["알수없는성분"], {}) == ["알수없는성분"]


def test_중복은_표준명_기준으로_합친다():
    alias_map = {normalize_key("니아신아마이드"): "나이아신아마이드"}
    합친 = resolve_canonical(["나이아신아마이드", "니아신아마이드"], alias_map)
    assert 합친 == ["나이아신아마이드"]


def test_빈_값과_공백은_거른다():
    assert resolve_canonical(["", "  ", "글리세린"], {}) == ["글리세린"]


def test_순서를_유지한다():
    assert resolve_canonical(["세라마이드", "글리세린"], {}) == ["세라마이드", "글리세린"]
