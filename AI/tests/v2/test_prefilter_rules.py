"""후보 거르기 규칙이 지켜야 할 성질.

모르는 것을 빼면 성분 정보가 없는 상품은 영영 추천되지 않는다. 뺀 것을 버리면
사용자는 왜 결과가 적은지 모른다.
"""
from rules.prefilter import apply

_보유 = [
    {"user_product_id": "u1", "product_id": "o1", "name": "레티놀 세럼"},
    {"user_product_id": "u2", "product_id": "o2", "name": "비타민 토너"},
]
_이름 = {"p1": "쿠션", "p2": "AHA 크림", "p3": "비타민C 앰플", "o1": "레티놀 세럼"}


def _후보(*ids, **값):
    return [{"product_id": pid, "source": "vector", "similarity": 0.5, **값} for pid in ids]


def _쌍(보유_id, 수준, 조언=None):
    return {"user_product_id": 보유_id, "ingredient_a": "레티놀", "ingredient_b": "AHA",
            "level": 수준, "advice": 조언, "schedule": None}


def test_이미_쓰는_제품은_뺀다():
    결과 = apply(_후보("o1", "p1"), _보유, {}, _이름)
    assert [c["product_id"] for c in 결과.candidates] == ["p1"]
    assert 결과.excluded == [{"product_id": "o1", "name": "레티놀 세럼", "reason": "OWNED",
                             "detail": "이미 쓰고 계신 제품이에요"}]


def test_함께_쓰면_안_되는_조합이_하나라도_있으면_뺀다():
    충돌 = {"p2": [_쌍("u2", "SEPARATE"), _쌍("u1", "AVOID", "같이 쓰면 자극이 심해요")]}
    결과 = apply(_후보("p1", "p2"), _보유, 충돌, _이름)
    assert [c["product_id"] for c in 결과.candidates] == ["p1"]
    assert 결과.excluded == [{"product_id": "p2", "name": "AHA 크림", "reason": "CONFLICT",
                             "detail": "레티놀 세럼과 함께 쓰지 않는 게 좋아요"}]
    assert 결과.conflict_marks == {}


def test_시간대만_나누면_되면_남기고_배지를_단다():
    충돌 = {"p3": [_쌍("u1", "SEPARATE", "레티놀은 저녁에, 비타민C는 아침에 쓰세요"),
                  _쌍("u2", "SEPARATE")]}
    결과 = apply(_후보("p3"), _보유, 충돌, _이름)
    assert [c["product_id"] for c in 결과.candidates] == ["p3"]
    assert 결과.excluded == []
    assert 결과.conflict_marks == {"p3": [
        {"user_product_id": "u1", "name": "레티놀 세럼", "level": "SEPARATE",
         "advice": "레티놀은 저녁에, 비타민C는 아침에 쓰세요"},
        # 조언이 없으면 보유 제품 이름으로 만든다. 받침이 없으면 '와'
        {"user_product_id": "u2", "name": "비타민 토너", "level": "SEPARATE",
         "advice": "비타민 토너와 시간대를 나눠 쓰세요"},
    ]}


def test_같은_보유_제품과_걸린_쌍이_여럿이면_배지는_하나다():
    충돌 = {"p3": [_쌍("u1", "SEPARATE", "첫 조언"), _쌍("u1", "SEPARATE", "둘째 조언")]}
    결과 = apply(_후보("p3"), _보유, 충돌, _이름)
    assert [m["advice"] for m in 결과.conflict_marks["p3"]] == ["첫 조언"]


def test_성분을_모르면_남긴다():
    결과 = apply(_후보("p1"), _보유, {"p1": []}, _이름)
    assert [c["product_id"] for c in 결과.candidates] == ["p1"]
    assert 결과.excluded == [] and 결과.conflict_marks == {}


def test_기준_상품은_빼지_않고_판정을_따로_돌려준다():
    충돌 = {"o1": [_쌍("u2", "AVOID")], "p1": [_쌍("u1", "AVOID")]}
    결과 = apply(_후보("o1", "p1"), _보유, 충돌, _이름, keep_ids={"o1"})
    assert [c["product_id"] for c in 결과.candidates] == ["o1"]
    assert 결과.base_conflicts == {"o1": {"owned": True, "conflicts": [
        {"user_product_id": "u2", "name": "비타민 토너", "level": "AVOID",
         "advice": "비타민 토너와 함께 쓰지 않는 게 좋아요"},
    ]}}
    # 기준 상품이 아닌 후보는 그대로 판정한다
    assert [e["product_id"] for e in 결과.excluded] == ["p1"]


def test_문제없는_기준_상품은_따로_남기지_않는다():
    결과 = apply(_후보("p1"), _보유, {}, _이름, keep_ids={"p1"})
    assert 결과.base_conflicts == {}


def test_세트의_같은_상품은_칸마다_같은_판정을_받고_기록은_한_번이다():
    후보 = [*_후보("p2", slot_key="토너"), *_후보("p2", slot_key="크림"),
           *_후보("p3", slot_key="토너"), *_후보("p3", slot_key="크림")]
    충돌 = {"p2": [_쌍("u1", "AVOID")], "p3": [_쌍("u1", "SEPARATE")]}
    결과 = apply(후보, _보유, 충돌, _이름)
    assert [(c["product_id"], c["slot_key"]) for c in 결과.candidates] == [
        ("p3", "토너"), ("p3", "크림")]
    assert [e["product_id"] for e in 결과.excluded] == ["p2"]


def test_보유_제품이_없으면_아무것도_빼지_않는다():
    결과 = apply(_후보("p1", "p2"), [], {}, _이름)
    assert [c["product_id"] for c in 결과.candidates] == ["p1", "p2"]
