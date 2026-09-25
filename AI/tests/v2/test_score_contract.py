"""점수 계약이 지켜야 할 성질.

핵심은 None 과 0점의 구분이다. 여기가 틀어지면 어떤 요청에서는 모든 후보가
같은 만큼 깎여, 순위는 그럴듯한데 점수가 전부 낮게 나온다. 화면만 봐서는
알아채기 어려운 종류의 버그라 여기서 고정한다.
"""
import pytest
from pydantic import ValidationError

from contracts.query_spec import QuerySpec, RequestType
from contracts.score import (
    SCORE_LABELS,
    ScoreContext,
    ScoreItem,
    ScoredProduct,
    build_score,
)


def test_항목_점수는_0에서_100_사이다():
    with pytest.raises(ValidationError):
        ScoreItem(key="review", label="후기 일치", score=120, weight=0.5)


def test_총점은_0에서_100_사이다():
    with pytest.raises(ValidationError):
        ScoredProduct(product_id="p1", total=101)


def test_가중합으로_총점을_낸다():
    결과 = build_score("p1", {"budget_fit": 80, "review": 60}, {"budget_fit": 0.5, "review": 0.5})
    assert 결과.total == 70


def test_None_인_항목은_빠지고_나머지_가중치가_다시_1이_된다():
    """환경을 따지지 않는 요청이 따지는 요청보다 낮게 나오면 안 된다."""
    결과 = build_score(
        "p1",
        {"budget_fit": 80, "review": 60, "env_fit": None},
        {"budget_fit": 0.5, "review": 0.25, "env_fit": 0.25},
    )
    assert [항목.key for 항목 in 결과.breakdown] == ["budget_fit", "review"]
    assert sum(항목.weight for 항목 in 결과.breakdown) == pytest.approx(1.0)
    assert 결과.total == 73  # 80*(2/3) + 60*(1/3)


def test_None_과_0점은_다르게_계산된다():
    가중치 = {"budget_fit": 0.5, "env_fit": 0.5}
    빠짐 = build_score("p1", {"budget_fit": 80, "env_fit": None}, 가중치)
    영점 = build_score("p1", {"budget_fit": 80, "env_fit": 0}, 가중치)
    assert 빠짐.total == 80
    assert 영점.total == 40


def test_가중치가_0인_항목은_계산에서_빠진다():
    """value_seeking 이 아닌 요청에서 가성비 항목을 끄는 방법이다."""
    결과 = build_score(
        "p1",
        {"budget_fit": 80, "value_signal": 10},
        {"budget_fit": 1.0, "value_signal": 0.0},
    )
    assert [항목.key for 항목 in 결과.breakdown] == ["budget_fit"]
    assert 결과.total == 80


def test_쓸_항목이_없으면_0점_대신_예외다():
    """조용히 0점을 내보내면 설정 실수가 결과에 묻힌다."""
    with pytest.raises(ValueError):
        build_score("p1", {"env_fit": None}, {"env_fit": 0.5})


def test_비중이_큰_항목이_앞에_온다():
    결과 = build_score(
        "p1",
        {"budget_fit": 50, "review": 50, "personalization": 50},
        {"budget_fit": 0.2, "review": 0.5, "personalization": 0.3},
    )
    assert [항목.key for 항목 in 결과.breakdown] == ["review", "personalization", "budget_fit"]


def test_라벨은_공통표를_따른다():
    결과 = build_score("p1", {"personalization": 90}, {"personalization": 1.0})
    assert 결과.breakdown[0].label == SCORE_LABELS["personalization"] == "내 피부 적합"


def test_모르는_키는_키_이름을_라벨로_쓴다():
    """새 항목을 만들다 라벨 등록을 잊어도 점수 계산이 멈추지는 않는다."""
    결과 = build_score("p1", {"새항목": 70}, {"새항목": 1.0})
    assert 결과.breakdown[0].label == "새항목"


def test_컨텍스트는_job_id를_반드시_받는다():
    """리뷰 점수가 job 값을 못 읽어 0점이 되던 사고를 타입으로 막는다."""
    with pytest.raises(ValidationError):
        ScoreContext(user_id="u1", query_spec=QuerySpec(request_type=RequestType.SEARCH))

    ctx = ScoreContext(
        job_id="j1", user_id="u1", query_spec=QuerySpec(request_type=RequestType.SEARCH)
    )
    assert ctx.env_summary is None
