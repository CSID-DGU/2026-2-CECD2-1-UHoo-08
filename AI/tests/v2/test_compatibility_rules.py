"""성분 쌍 판정 규칙. DB 와 LLM 없이 돈다."""
from rules.compatibility import (
    AVOID,
    OK,
    SEPARATE,
    SEPARATE_SCHEDULE,
    check_compatibility,
    find_pairs,
    strongest,
)

규칙 = [
    {"ingredient_a": "글라이콜릭애씨드", "ingredient_b": "레티놀", "level": AVOID, "advice": "같이 쓰면 자극"},
    {"ingredient_a": "레티놀", "ingredient_b": "비타민C", "level": SEPARATE, "advice": "아침 비타민C, 저녁 레티놀"},
]


def test_규칙에_있는_쌍만_순서와_상관없이_찾는다():
    쌍들 = find_pairs(["비타민C", "판테놀"], ["레티놀"], 규칙)
    assert [(p["ingredient_a"], p["ingredient_b"], p["level"]) for p in 쌍들] == [("레티놀", "비타민C", SEPARATE)]
    assert 쌍들[0]["schedule"] == SEPARATE_SCHEDULE


def test_센_쌍이_먼저_온다():
    쌍들 = find_pairs(["레티놀"], ["비타민C", "글라이콜릭애씨드"], 규칙)
    assert [p["level"] for p in 쌍들] == [AVOID, SEPARATE]
    assert 쌍들[0]["schedule"] is None and 쌍들[0]["advice"] == "같이 쓰면 자극"


def test_같은_성분끼리는_충돌이_아니고_같은_쌍은_한_번만_센다():
    assert find_pairs(["레티놀"], ["레티놀"], 규칙) == []
    쌍들 = find_pairs(["레티놀", "비타민C"], ["비타민C", "레티놀"], 규칙)
    assert len(쌍들) == 1


def test_보유_제품마다_걸린_쌍에_보유_제품_id를_붙인다():
    보유 = [
        {"user_product_id": "u1", "product_id": "o1", "ingredients": ["레티놀"]},
        {"user_product_id": "u2", "product_id": "o2", "ingredients": ["판테놀"]},
        {"user_product_id": "u3", "product_id": "o3", "ingredients": ["글라이콜릭애씨드"]},
    ]
    상품 = {"product_id": "p1", "ingredients": ["비타민C", "레티놀"]}
    쌍들 = check_compatibility(보유, 상품, 규칙)
    assert [(p["user_product_id"], p["level"]) for p in 쌍들] == [("u3", AVOID), ("u1", SEPARATE)]


def test_같은_상품을_가지고_있으면_그_보유_제품과는_견주지_않는다():
    보유 = [{"user_product_id": "u1", "product_id": "p1", "ingredients": ["레티놀"]}]
    assert check_compatibility(보유, {"product_id": "p1", "ingredients": ["비타민C"]}, 규칙) == []


def test_가장_센_단계():
    assert strongest([]) == OK
    assert strongest([SEPARATE, AVOID, OK]) == AVOID
