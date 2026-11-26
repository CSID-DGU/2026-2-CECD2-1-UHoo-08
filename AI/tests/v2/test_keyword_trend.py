"""키워드 순위 → 제품 점수."""
from rules.keyword_extract import load_keywords
from rules.keyword_trend import product_keywords

D = load_keywords()


def prod(pid, name="", ingredients=None, concerns=None):
    return {"product_id": pid, "name": name,
            "feature_json": {"key_ingredient": ingredients or [], "skin_concern": concerns or []}}




def test_product_keywords_from_features_and_name():
    p = prod("x", "VT 피디알엔 에센스", ingredients=["판테놀"], concerns=["보습"])
    assert product_keywords(p, D) == {"pdrn": "name:피디알엔", "panthenol": "ingredient:판테놀",
                                      "hydration": "concern:보습"}


def test_feature_json_as_string():
    p = {"product_id": "x", "name": "크림", "feature_json": '{"key_ingredient": "병풀추출물"}'}
    assert product_keywords(p, D) == {"cica": "ingredient:병풀추출물"}


def test_product_without_keywords():
    assert product_keywords({"product_id": "x", "name": "립스틱", "feature_json": None}, D) == {}
