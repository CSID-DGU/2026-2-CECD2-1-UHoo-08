"""backfill_product_data 의 --types 단위 테스트. 추출, 파서, Supabase 는 가짜로 바꾼다."""
import json
import types

import pytest

import scripts.backfill_product_data as 백필


def _행(category, product_type, **값):
    return {"product_id": "p1", "name": "상품", "brand": "B", "category": category,
            "feature_json": json.dumps({"product_type": product_type, "finish": "매트"}), **값}


@pytest.mark.parametrize("category, product_type, 대상", [
    ("skincare", None, True),
    ("skincare", "핸드크림", True),
    ("base", "토너", True),
    ("blush", "블러셔", True),
    ("", "아이라이너", True),
    ("skincare", "앰플", False),
    ("skincare", "스킨", False),
    ("lip", ["립세럼", "틴트"], False),
])
def test_종류를_다시_채울_상품을_고른다(category, product_type, 대상):
    assert 백필._needs_types(_행(category, product_type)) is 대상


class _가짜_DB:
    def __init__(self):
        self.저장 = []

    def table(self, 이름):
        return self

    def update(self, 값):
        self.저장.append(값)
        return self

    def eq(self, *인자):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


@pytest.fixture
def 바꿔치기(monkeypatch):
    db = _가짜_DB()
    상태 = {"추출": {}, "받은_카테고리": None, "파서": None}
    monkeypatch.setattr(백필, "get_supabase", lambda: db)

    def 추출(상품):
        상태["받은_카테고리"] = 상품.category
        return {"product_features": 상태["추출"]}

    monkeypatch.setattr(백필, "enrich_product", 추출)
    monkeypatch.setattr(백필, "_classify_category", lambda row: 상태["파서"])
    return db, 상태


def test_카테고리가_그대로면_종류만_바꾸고_다른_특징은_둔다(바꿔치기):
    db, 상태 = 바꿔치기
    상태["추출"] = {"product_type": "스킨", "finish": "글로우"}

    assert 백필._refill_types(_행("skincare", None)) == "skincare 토너"
    assert db.저장 == [{"feature_json": json.dumps({"product_type": "토너", "finish": "매트"}, ensure_ascii=False)}]
    assert 상태["받은_카테고리"] == {"main": "skincare", "sub": ""}


def test_종류가_여럿이면_표준_이름_목록으로_저장한다(바꿔치기):
    db, 상태 = 바꿔치기
    상태["추출"] = {"product_type": ["립에센스", "틴트", "립밤"]}

    백필._refill_types(_행("lip", "립"))
    assert json.loads(db.저장[0]["feature_json"])["product_type"] == ["립세럼", "틴트"]


def test_예전_카테고리는_지금_카테고리로_바꾸고_특징을_통째로_바꾼다(바꿔치기):
    db, 상태 = 바꿔치기
    상태["추출"] = {"product_type": "블러쉬", "finish": "쉬머", "personal_color": "쿨톤"}

    assert 백필._refill_types(_행("blush", None)) == "cheek 블러셔"
    assert db.저장[0]["category"] == "cheek"
    assert json.loads(db.저장[0]["feature_json"]) == {
        "product_type": "블러셔", "finish": "쉬머", "personal_color": "쿨톤"}


def test_카테고리가_비면_이름으로_정한다(바꿔치기):
    db, 상태 = 바꿔치기
    상태["파서"] = "eye"
    상태["추출"] = {"product_type": "아이라이너", "waterproof": True}

    assert 백필._refill_types(_행("", None)) == "eye 아이라이너"
    assert db.저장[0]["category"] == "eye"


def test_카테고리를_정하지_못하면_저장하지_않는다(바꿔치기):
    db, 상태 = 바꿔치기

    with pytest.raises(ValueError, match="카테고리"):
        백필._refill_types(_행("", None))
    assert db.저장 == []


def test_카테고리가_그대로인데_목록의_종류를_못_찾으면_저장하지_않는다(바꿔치기):
    db, 상태 = 바꿔치기
    상태["추출"] = {"product_type": "핸드크림"}

    with pytest.raises(ValueError, match="핸드크림"):
        백필._refill_types(_행("skincare", None))
    assert db.저장 == []


def test_특징을_받지_못하면_저장하지_않는다(바꿔치기):
    db, 상태 = 바꿔치기

    with pytest.raises(ValueError, match="특징"):
        백필._refill_types(_행("blush", None))
    assert db.저장 == []


def test_추출_힌트의_종류는_목록이면_첫_번째를_쓴다():
    assert 백필._product_type(_행("lip", ["립세럼", "틴트"])) == "립세럼"
    assert 백필._product_type(_행("lip", None)) is None
