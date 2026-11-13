"""추천 기준에 따라 사용자 맥락을 어떻게 채우는지 본다.

다른 사람 기준에서 본인 프로필이 섞이면 받을 사람이 아니라 요청한 사람에게
맞는 제품이 나온다.
"""
import sys
import types

import pytest

from services import user_context
from services.preference_apply import 기본_가중치


class 가짜테이블:
    def __init__(self, 이름, 기록, 행들):
        self.이름 = 이름
        self.기록 = 기록
        self.행들 = 행들

    def select(self, 칼럼):
        self.기록.setdefault("select", {})[self.이름] = 칼럼
        return self

    def eq(self, 칼럼, 값):
        self.기록.setdefault("eq", []).append((self.이름, 칼럼, 값))
        return self

    def limit(self, n):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.행들.get(self.이름, []))


@pytest.fixture
def DB(monkeypatch):
    def 세우기(**행들):
        import db

        기록: dict = {}
        모듈 = types.SimpleNamespace(
            get_supabase=lambda: types.SimpleNamespace(
                table=lambda 이름: 가짜테이블(이름, 기록, 행들)
            )
        )
        monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
        monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
        return 기록

    return 세우기


_본인 = {
    "skin_type": "OILY_DEHYDRATED", "skin_concerns": ["SEBUM"], "personal_color": "SPRING_WARM",
    "region": "서울", "search_purpose": "DAILY", "price_tolerance_percent": 10,
}


@pytest.mark.asyncio
async def test_본인_기준은_users에서_읽는다(DB):
    기록 = DB(users=[_본인])
    맥락 = await user_context.load("u1", "SELF", None)

    assert 맥락["user_profile"] == _본인
    assert ("users", "id", "u1") in 기록["eq"]


@pytest.mark.asyncio
async def test_전체_인기_기준도_본인_프로필을_읽는다(DB):
    DB(users=[_본인])
    맥락 = await user_context.load("u1", "POPULAR", None)
    assert 맥락["user_profile"]["skin_type"] == "OILY_DEHYDRATED"


@pytest.mark.asyncio
async def test_다른_사람_기준은_화면_값을_옮기고_지역은_비운다(DB):
    기록 = DB(users=[_본인])
    맥락 = await user_context.load("u1", "OTHER", {
        "relation": "엄마", "personalColor": "AUTUMN_WARM",
        "skinType": "DRY", "skinConcerns": ["WRINKLE"],
    })

    assert 맥락["user_profile"] == {
        "relation": "엄마", "personal_color": "AUTUMN_WARM",
        "skin_type": "DRY", "skin_concerns": ["WRINKLE"],
        "region": None, "search_purpose": None, "price_tolerance_percent": None,
    }
    # 요청한 사람의 프로필은 읽지 않는다
    assert "users" not in 기록.get("select", {})


@pytest.mark.asyncio
async def test_다른_사람_기준인데_조건이_없으면_빈_프로필이다(DB):
    DB()
    맥락 = await user_context.load("u1", "OTHER", None)
    assert 맥락["user_profile"]["skin_type"] is None
    assert 맥락["user_profile"]["skin_concerns"] == []


@pytest.mark.asyncio
async def test_사용자가_없으면_빈_프로필로_진행한다(DB):
    DB()
    맥락 = await user_context.load("u1", "SELF", None)
    assert all(맥락["user_profile"][칸] is None for 칸 in ("skin_type", "region"))
    assert 맥락["user_profile"]["skin_concerns"] == []


@pytest.mark.asyncio
async def test_빈_값은_빈_프로필_기본값을_지킨다(DB):
    DB(users=[{**_본인, "skin_concerns": None}])
    맥락 = await user_context.load("u1", "SELF", None)
    assert 맥락["user_profile"]["skin_concerns"] == []


@pytest.mark.asyncio
async def test_저장된_가중치를_읽는다(DB):
    기록 = DB(users=[_본인], user_preference_weights=[{"weights": {"review": 0.4}}])
    맥락 = await user_context.load("u1", "SELF", None)

    assert 맥락["weight_prior"] == {"review": 0.4}
    assert ("user_preference_weights", "user_id", "u1") in 기록["eq"]


@pytest.mark.asyncio
async def test_다른_사람_기준도_요청한_사람의_가중치를_쓴다(DB):
    DB(user_preference_weights=[{"weights": {"review": 0.4}}])
    맥락 = await user_context.load("u1", "OTHER", {"skinType": "DRY"})
    assert 맥락["weight_prior"] == {"review": 0.4}


@pytest.mark.asyncio
async def test_가중치_행이_없으면_기본_가중치의_복사본이다(DB):
    DB(users=[_본인])
    맥락 = await user_context.load("u1", "SELF", None)

    assert 맥락["weight_prior"] == 기본_가중치
    맥락["weight_prior"]["review"] = 99
    assert 기본_가중치["review"] != 99
