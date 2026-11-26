"""키워드 순위 → 제품 점수."""
from rules.keyword_extract import load_keywords
from rules.keyword_trend import TOP_N, KeywordRank, keyword_points, product_keywords, product_scores

D = load_keywords()


def prod(pid, name="", ingredients=None, concerns=None):
    return {"product_id": pid, "name": name,
            "feature_json": {"key_ingredient": ingredients or [], "skin_concern": concerns or []}}


RANKS = [KeywordRank("pdrn", 1, mention_count=3, engagement=300), KeywordRank("hydration", 2, mention_count=2)]


def test_points_follow_rank():
    assert keyword_points(RANKS) == {"pdrn": (1, TOP_N), "hydration": (2, TOP_N - 1)}


def test_ranks_outside_top_n_get_no_points():
    assert keyword_points([KeywordRank("pdrn", TOP_N), KeywordRank("cica", TOP_N + 1)]) == {"pdrn": (TOP_N, 1)}


def test_product_keywords_from_features_and_name():
    p = prod("x", "VT 피디알엔 에센스", ingredients=["판테놀"], concerns=["보습"])
    assert product_keywords(p, D) == {"pdrn": "name:피디알엔", "panthenol": "ingredient:판테놀",
                                      "hydration": "concern:보습"}


def test_feature_json_as_string():
    p = {"product_id": "x", "name": "크림", "feature_json": '{"key_ingredient": "병풀추출물"}'}
    assert product_keywords(p, D) == {"cica": "ingredient:병풀추출물"}


def test_product_without_keywords():
    assert product_keywords({"product_id": "x", "name": "립스틱", "feature_json": None}, D) == {}


def test_product_score_sums_ranked_keyword_points():
    products = [
        prod("both", "PDRN 수분크림", concerns=["보습"]),
        prod("pdrn", "PDRN 앰플"),
        prod("pdrn2", "pdrn 토너"),
        prod("panth", "판테놀 밤", ingredients=["판테놀"]),   # 판테놀은 순위 밖이라 0점 → 빠진다
        prod("none", "립스틱"),
    ]
    scores = product_scores(RANKS, products, D)

    assert [(s.product_id, s.score) for s in scores] == [("both", TOP_N + TOP_N - 1), ("pdrn", TOP_N), ("pdrn2", TOP_N)]
    assert [k["keyword_id"] for k in scores[0].keywords] == ["pdrn", "hydration"]
    assert scores[0].mention_count == 5 and scores[1].engagement == 300


def test_ties_keep_product_id_order():
    scores = product_scores(RANKS, [prod("b", "PDRN"), prod("a", "PDRN")], D)
    assert [s.product_id for s in scores] == ["a", "b"]
