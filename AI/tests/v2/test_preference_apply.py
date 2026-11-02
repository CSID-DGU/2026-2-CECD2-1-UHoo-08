"""피드백과 조건 수정이 가중치로 옮겨지는 규칙을 본다.

DB 는 메모리 대역으로 둔다. 쿼리 조건은 test_preference_store.py 가 본다.
"""
from datetime import datetime, timedelta, timezone

import pytest

from api.internal.v2 import feedback
from contracts.score import SCORE_LABELS
from services import preference_apply

지금 = datetime(2026, 11, 3, tzinfo=timezone.utc)


def _결과(*항목들):
    """p1 의 항목별 점수가 담긴 job 결과."""
    return {"items": [{
        "productId": "p1",
        "breakdown": [{"key": 키, "score": 점수} for 키, 점수 in 항목들],
    }]}


def _피드백(id=1, vote="DOWN", reason_tags=(), job_id="j1", product_id="p1"):
    return {"id": id, "job_id": job_id, "product_id": product_id,
            "vote": vote, "reason_tags": list(reason_tags)}


class 가짜저장소:
    def __init__(self, 피드백=(), 결과=None, 조건수정=(), 패턴변경=(), 먼저_가져감=()):
        self.피드백 = {행["id"]: 행 for 행 in 피드백}
        self.결과 = 결과
        self.조건수정 = list(조건수정)
        self.패턴변경 = list(패턴변경)
        self.먼저_가져감 = set(먼저_가져감)
        self.변경: list[dict] = []
        self.뺀_피드백: list[int] = []
        self.저장: dict | None = None

    async def load_unapplied_feedback_ids(self, user_id):
        return list(self.피드백)

    async def claim_feedback(self, feedback_id, now):
        return None if feedback_id in self.먼저_가져감 else self.피드백[feedback_id]

    async def retire_feedback_changes(self, user_id, feedback_id, now):
        self.뺀_피드백.append(feedback_id)

    async def load_job_result(self, job_id):
        return self.결과

    async def insert_change(self, user_id, source, source_ref, deltas, text):
        self.변경.append({"source": source, "source_ref": source_ref,
                         "deltas": deltas, "text": text})

    async def load_refine_presets_since(self, user_id, since):
        self.기준일 = since
        return self.조건수정

    async def load_pattern_changes(self, user_id):
        return self.패턴변경

    async def load_active_changes(self, user_id):
        return self.변경

    async def save_weights(self, user_id, weights, source_counts, now):
        self.저장 = {"weights": weights, "source_counts": source_counts}


@pytest.fixture
def 저장소(monkeypatch):
    def 세우기(**값):
        가짜 = 가짜저장소(**값)
        monkeypatch.setattr(preference_apply, "preference_store", 가짜)
        return 가짜

    return 세우기


def test_기본_가중치의_키가_점수_항목과_같다():
    assert set(preference_apply.기본_가중치) == set(SCORE_LABELS)


@pytest.mark.asyncio
@pytest.mark.parametrize("이유, 변화량, 문장", [
    ("TOO_EXPENSIVE", {"budget_fit": 0.05, "value_signal": 0.05},
     "'너무 비싸요' 피드백으로 가격 비중 ↑"),
    ("NOT_MY_SKIN", {"personalization": 0.05},
     "'내 피부에 안 맞을 것 같아요' 피드백으로 피부 적합 비중 ↑"),
    ("BAD_REVIEWS", {"review": 0.05}, "'후기가 별로예요' 피드백으로 후기 비중 ↑"),
])
async def test_이유별_변화량과_문장(저장소, 이유, 변화량, 문장):
    가짜 = 저장소(피드백=[_피드백(reason_tags=[이유])])
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경 == [
        {"source": "FEEDBACK", "source_ref": "1", "deltas": 변화량, "text": 문장},
    ]


@pytest.mark.asyncio
async def test_이유가_여러_개면_한_건으로_묶는다(저장소):
    가짜 = 저장소(피드백=[_피드백(reason_tags=["BAD_REVIEWS", "TOO_EXPENSIVE"])])
    await preference_apply.apply_feedback("u1", 지금)
    assert len(가짜.변경) == 1
    assert 가짜.변경[0]["deltas"] == {"budget_fit": 0.05, "value_signal": 0.05, "review": 0.05}
    assert 가짜.변경[0]["text"] == "'너무 비싸요', '후기가 별로예요' 피드백으로 가격, 후기 비중 ↑"


@pytest.mark.asyncio
async def test_좋아요는_강점_항목을_올린다(저장소):
    가짜 = 저장소(
        피드백=[_피드백(vote="UP")],
        결과=_결과(("review", 90), ("personalization", 80), ("budget_fit", 40)),
    )
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경[0]["deltas"] == {"review": 0.025, "personalization": 0.025}
    assert 가짜.변경[0]["text"] == "'좋아요' 피드백으로 후기, 피부 적합 비중 ↑"


@pytest.mark.asyncio
async def test_이유_없는_별로예요는_강점_항목을_내린다(저장소):
    가짜 = 저장소(피드백=[_피드백()], 결과=_결과(("review", 90), ("budget_fit", 40)))
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경[0]["deltas"] == {"review": -0.025}
    assert 가짜.변경[0]["text"] == "'별로예요' 피드백으로 후기 비중 ↓"


@pytest.mark.asyncio
async def test_지운_이유만_저장된_피드백은_이유_없는_별로예요로_본다(저장소):
    가짜 = 저장소(
        피드백=[_피드백(reason_tags=["ALREADY_HAVE_SIMILAR"])],
        결과=_결과(("review", 90), ("budget_fit", 40)),
    )
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경[0]["deltas"] == {"review": -0.025}


@pytest.mark.asyncio
@pytest.mark.parametrize("결과", [
    None,
    {"items": []},
    {"items": [{"productId": "다른제품", "breakdown": [{"key": "review", "score": 90}]}]},
    {"items": [{"productId": "p1", "breakdown": []}]},
    _결과(("review", 50), ("budget_fit", 50)),
    # 기본값이 0 인 항목만 강점이면 곱해도 움직이지 않는다
    _결과(("value_signal", 90), ("review", 10)),
])
async def test_움직일_항목이_없으면_변경을_만들지_않는다(저장소, 결과):
    가짜 = 저장소(피드백=[_피드백(vote="UP")], 결과=결과)
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경 == []
    assert 가짜.저장["weights"] == preference_apply.기본_가중치


@pytest.mark.asyncio
async def test_다른_호출이_먼저_가져간_피드백은_건너뛴다(저장소):
    가짜 = 저장소(피드백=[_피드백(reason_tags=["BAD_REVIEWS"])], 먼저_가져감=[1])
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경 == [] and 가짜.뺀_피드백 == []


@pytest.mark.asyncio
async def test_다시_누른_피드백은_이전_변경을_뺀_뒤_만든다(저장소):
    가짜 = 저장소(피드백=[_피드백(reason_tags=["BAD_REVIEWS"])])
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.뺀_피드백 == [1]
    assert len(가짜.변경) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("횟수, 만듦", [(2, False), (3, True), (4, True)])
async def test_같은_선택지를_3번_이상_고르면_패턴으로_만든다(저장소, 횟수, 만듦):
    가짜 = 저장소(조건수정=[["CHEAPER"]] * 횟수)
    await preference_apply.apply_feedback("u1", 지금)
    if 만듦:
        assert 가짜.변경 == [{
            "source": "REFINE_PATTERN", "source_ref": "CHEAPER",
            "deltas": {"budget_fit": 0.05, "value_signal": 0.05},
            "text": "'더 저렴하게'를 자주 고르셔서 가격 비중 ↑",
        }]
    else:
        assert 가짜.변경 == []


@pytest.mark.asyncio
async def test_민감성_패턴의_문장(저장소):
    가짜 = 저장소(조건수정=[["SENSITIVE_OK"]] * 3)
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경[0]["text"] == "'민감성도 괜찮은'을 자주 고르셔서 피부 적합 비중 ↑"
    assert 가짜.변경[0]["deltas"] == {"personalization": 0.05}


@pytest.mark.asyncio
async def test_패턴은_최근_30일만_읽는다(저장소):
    가짜 = 저장소()
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.기준일 == 지금 - timedelta(days=30)


@pytest.mark.asyncio
async def test_한_번의_조건_수정에서_중복은_한_번으로_센다(저장소):
    가짜 = 저장소(조건수정=[["CHEAPER", "CHEAPER", "CHEAPER"]])
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경 == []


@pytest.mark.asyncio
async def test_점수_항목이_없는_선택지는_패턴이_되지_않는다(저장소):
    가짜 = 저장소(조건수정=[["UNSCENTED"]] * 5)
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.변경 == []


@pytest.mark.asyncio
@pytest.mark.parametrize("되돌린_때, 만듦", [
    (None, False),
    ((지금 - timedelta(days=29)).isoformat(), False),
    ((지금 - timedelta(days=31)).isoformat(), True),
])
async def test_반영_중이거나_최근_되돌린_패턴은_만들지_않는다(저장소, 되돌린_때, 만듦):
    가짜 = 저장소(
        조건수정=[["CHEAPER"]] * 3,
        패턴변경=[{"source_ref": "CHEAPER", "reverted_at": 되돌린_때}],
    )
    await preference_apply.apply_feedback("u1", 지금)
    assert bool(가짜.변경) is 만듦


@pytest.mark.asyncio
async def test_다른_패턴의_되돌림은_영향이_없다(저장소):
    가짜 = 저장소(
        조건수정=[["CHEAPER"]] * 3,
        패턴변경=[{"source_ref": "SENSITIVE_OK", "reverted_at": None}],
    )
    await preference_apply.apply_feedback("u1", 지금)
    assert [변경["source_ref"] for 변경 in 가짜.변경] == ["CHEAPER"]


def test_되돌리지_않은_변경을_기본값에_더한다():
    가중치, 신호_수 = preference_apply._합산([
        {"source": "FEEDBACK", "deltas": {"review": 0.05}},
        {"source": "FEEDBACK", "deltas": {"review": -0.025, "value_signal": 0.05}},
        {"source": "REFINE_PATTERN", "deltas": {"budget_fit": 0.05}},
    ])
    assert 가중치["review"] == 0.275
    assert 가중치["value_signal"] == 0.05
    assert 가중치["budget_fit"] == 0.3
    assert 가중치["env_fit"] == 0.0
    assert 신호_수 == {"feedback": 2, "refine": 1}


def test_가중치는_0에서_1_사이로_제한한다():
    가중치, _ = preference_apply._합산([
        {"source": "FEEDBACK", "deltas": {"review": 5.0, "budget_fit": -5.0}},
    ])
    assert 가중치["review"] == 1.0
    assert 가중치["budget_fit"] == 0.0


@pytest.mark.asyncio
async def test_변경이_없으면_기본값으로_되돌아간다(저장소):
    """마지막 변경을 되돌리면 이전 합계가 남으면 안 된다."""
    가짜 = 저장소()
    await preference_apply.apply_feedback("u1", 지금)
    assert 가짜.저장 == {
        "weights": preference_apply.기본_가중치,
        "source_counts": {"feedback": 0, "refine": 0},
    }


@pytest.mark.asyncio
async def test_경로의_배경_작업은_실패해도_올리지_않는다(monkeypatch):
    async def 터짐(user_id):
        raise RuntimeError("DB 끊김")

    monkeypatch.setattr(feedback.preference_apply, "apply_feedback", 터짐)
    await feedback._반영("u1")
