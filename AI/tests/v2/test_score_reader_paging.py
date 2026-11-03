"""협업 추천의 조회가 1,000행 제한에 잘리지 않는지 본다.

가짜 DB도 실제처럼 한 번에 1,000행까지만 돌려준다. 첫 응답만 쓰면 뒷부분이 조용히 빠진다.
"""
import importlib
import sys
import types

import pytest

한번에_돌려주는_행 = 1000


class 가짜쿼리:
    def __init__(self, 요청들, 행들, 상한):
        self.요청 = {"eq": [], "neq": [], "in": [], "order": [], "range": None}
        요청들.append(self.요청)
        self.행들 = 행들
        self.상한 = 상한

    def select(self, *_):
        return self

    def eq(self, 열, 값):
        self.요청["eq"].append((열, 값))
        self.행들 = [행 for 행 in self.행들 if 행.get(열) == 값]
        return self

    def neq(self, 열, 값):
        self.요청["neq"].append((열, 값))
        self.행들 = [행 for 행 in self.행들 if 행.get(열) != 값]
        return self

    def in_(self, 열, 값들):
        self.요청["in"].append((열, list(값들)))
        self.행들 = [행 for 행 in self.행들 if 행.get(열) in set(값들)]
        return self

    def order(self, 열, **_):
        self.요청["order"].append(열)
        self.행들 = sorted(self.행들, key=lambda 행: 행[열])
        return self

    def range(self, 시작, 끝):
        self.요청["range"] = (시작, 끝)
        return self

    def execute(self):
        시작, 끝 = self.요청["range"] or (0, self.상한 - 1)
        끝 = min(끝, 시작 + self.상한 - 1)
        return types.SimpleNamespace(data=self.행들[시작 : 끝 + 1])


@pytest.fixture
def 읽기(monkeypatch):
    """대역 DB를 물린 score_reader 와 요청 기록을 돌려준다. 끝나면 대역을 물린 모듈을 치운다."""
    import db

    모듈 = types.SimpleNamespace(get_supabase=None)
    monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
    monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
    sys.modules.pop("db.score_reader", None)
    score_reader = importlib.import_module("db.score_reader")

    def 세우기(상한=한번에_돌려주는_행, **테이블들):
        요청들: list = []

        def get_supabase():
            return types.SimpleNamespace(table=lambda 이름: 가짜쿼리(요청들, 테이블들.get(이름, []), 상한))

        monkeypatch.setattr(score_reader, "get_supabase", get_supabase)
        return score_reader, 요청들

    yield 세우기
    sys.modules.pop("db.score_reader", None)
    if hasattr(db, "score_reader"):
        del db.score_reader


def 사용자(수, **열):
    return [{"id": f"u{번호:05d}", **열} for 번호 in range(수)]


def 사용_기록(수, 사용자_수=1):
    return [
        {
            "id": f"up{번호:05d}",
            "user_id": f"u{번호 % 사용자_수:05d}",
            "product_id": f"p{번호}",
            "usage_type": "USING",
            "rating": 5,
            "created_at": None,
        }
        for 번호 in range(수)
    ]


@pytest.mark.parametrize(
    "수, 요청_수",
    [(0, 1), (999, 2), (1000, 2), (1001, 3), (2500, 4)],
)
def test_비슷한_사용자를_끝까지_읽는다(읽기, 수, 요청_수):
    score_reader, 요청들 = 읽기(users=사용자(수, skin_type="DRY"))

    결과 = score_reader.get_similar_user_ids("DRY", None, "본인")

    assert 결과 == [f"u{번호:05d}" for 번호 in range(수)]
    assert len(요청들) == 요청_수


def test_페이지마다_정렬과_다음_구간을_요청한다(읽기):
    score_reader, 요청들 = 읽기(users=사용자(1500, skin_type="DRY"))

    score_reader.get_similar_user_ids("DRY", None, "본인")

    assert [요청["range"] for 요청 in 요청들] == [(0, 999), (1000, 1999), (1500, 2499)]
    assert all(요청["order"] == ["id"] for 요청 in 요청들)


def test_서버_상한이_더_낮아도_건너뛰지_않고_끝까지_읽는다(읽기):
    score_reader, 요청들 = 읽기(상한=300, users=사용자(700, skin_type="DRY"))

    결과 = score_reader.get_similar_user_ids("DRY", None, "본인")

    assert 결과 == [f"u{번호:05d}" for 번호 in range(700)]
    assert [요청["range"][0] for 요청 in 요청들] == [0, 300, 600, 700]


def test_본인_제외와_필터가_모든_페이지에_유지된다(읽기):
    행들 = 사용자(1500, skin_type="DRY", personal_color="WARM")
    행들 += [{"id": "z다른피부", "skin_type": "OILY", "personal_color": "WARM"}]
    행들 += [{"id": "z다른색", "skin_type": "DRY", "personal_color": "COOL"}]
    score_reader, 요청들 = 읽기(users=행들)

    결과 = score_reader.get_similar_user_ids("DRY", "WARM", "u00003")

    assert len(결과) == 1499
    assert "u00003" not in 결과
    assert "z다른피부" not in 결과 and "z다른색" not in 결과
    for 요청 in 요청들:
        assert 요청["eq"] == [("skin_type", "DRY"), ("personal_color", "WARM")]
        assert 요청["neq"] == [("id", "u00003")]


def test_피부와_색이_없으면_필터_없이_본인만_뺀다(읽기):
    score_reader, 요청들 = 읽기(users=사용자(3))

    assert score_reader.get_similar_user_ids(None, None, "u00001") == ["u00000", "u00002"]
    assert 요청들[0]["eq"] == []


def test_인기_제품은_1000명_뒤_사용자의_평점도_센다(읽기):
    사용자들 = 사용자(1500, skin_type="DRY")
    기록 = [
        {
            "id": "up1",
            "user_id": "u01400",
            "product_id": "뒤쪽제품",
            "usage_type": "USING",
            "rating": 5,
            "created_at": None,
        }
    ]
    score_reader, _ = 읽기(users=사용자들, user_products=기록)

    assert score_reader.get_popular_products_by_skin_type("DRY") == ["뒤쪽제품"]


def test_인기_제품은_그_피부_타입_사용자가_없으면_빈_목록이다(읽기):
    score_reader, 요청들 = 읽기(users=사용자(3, skin_type="OILY"))

    assert score_reader.get_popular_products_by_skin_type("DRY") == []
    assert len(요청들) == 1


@pytest.mark.parametrize("수, 요청_수", [(1000, 2), (2500, 4)])
def test_사용_기록을_끝까지_읽는다(읽기, 수, 요청_수):
    score_reader, 요청들 = 읽기(user_products=사용_기록(수))

    결과 = score_reader.get_user_products_by_users(["u00000"])

    assert len(결과) == 수
    assert len(요청들) == 요청_수
    assert set(결과[0]) == {"id", "user_id", "product_id", "usage_type", "rating", "created_at"}


def test_사용자가_없으면_사용_기록을_조회하지_않는다(읽기):
    score_reader, 요청들 = 읽기()

    assert score_reader.get_user_products_by_users([]) == []
    assert 요청들 == []


@pytest.mark.parametrize(
    "사용자_수, 조각_수",
    [(1, 1), (200, 1), (201, 2), (450, 3)],
)
def test_사용자_목록을_나눠_모두_한_번씩_조회한다(읽기, 사용자_수, 조각_수):
    score_reader, 요청들 = 읽기(user_products=사용_기록(사용자_수, 사용자_수))
    아이디들 = [f"u{번호:05d}" for 번호 in range(사용자_수)]

    결과 = score_reader.get_user_products_by_users(아이디들)

    조각들 = [요청["in"][0][1] for 요청 in 요청들 if 요청["range"][0] == 0]
    assert len(조각들) == 조각_수
    assert all(len(조각) <= 200 for 조각 in 조각들)
    assert [아이디 for 조각 in 조각들 for 아이디 in 조각] == 아이디들
    assert len(결과) == 사용자_수


def test_나눈_조각_안에서_1000행을_넘어도_끝까지_읽는다(읽기):
    # 첫 조각의 사용자 200명이 2,400행, 다음 조각의 50명이 600행을 가진다
    score_reader, 요청들 = 읽기(user_products=사용_기록(3000, 250))
    아이디들 = [f"u{번호:05d}" for 번호 in range(250)]

    결과 = score_reader.get_user_products_by_users(아이디들)

    assert len(결과) == 3000
    assert len({행["id"] for 행 in 결과}) == 3000
    assert [요청["range"] for 요청 in 요청들] == [
        (0, 999),
        (1000, 1999),
        (2000, 2999),
        (2400, 3399),
        (0, 999),
        (600, 1599),
    ]


def test_나눠_읽어도_결과는_id_순서다(읽기):
    # 앞 조각의 사용자가 뒤쪽 id 를 가진다. 조각 순서대로 이어 붙이면 순서가 뒤집힌다
    기록 = 사용_기록(2)
    기록[0]["user_id"] = "u00300"
    기록[1]["user_id"] = "u00000"
    score_reader, _ = 읽기(user_products=기록)
    아이디들 = [f"u{번호:05d}" for 번호 in range(301)]

    결과 = score_reader.get_user_products_by_users(아이디들)

    assert [행["id"] for 행 in 결과] == ["up00000", "up00001"]
