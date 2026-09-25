"""점수의 출력 모양과 scorer 플러그인 인터페이스.

점수 항목은 앞으로 늘어난다(env_fit, value_signal, …). 항목이 늘 때마다
Score 노드와 BE 저장 형식과 FE 화면을 같이 고쳐야 한다면 아무도 항목을
추가하지 않게 된다. 그래서 breakdown 을 고정 키가 아니라 리스트로 둔다.
항목이 늘어도 고칠 곳은 scorers/ 에 파일 하나 추가하는 것뿐이다.
"""
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from contracts.query_spec import QuerySpec

# 항목 키 → 화면에 보일 이름. FE가 이 label 을 그대로 그린다.
# 키를 바꾸면 저장된 과거 결과와 이어지지 않으므로 이름만 바꾼다.
SCORE_LABELS: dict[str, str] = {
    "budget_fit": "예산 적합",
    "price_value": "가격 대비 가치",
    "review": "후기 일치",
    "personalization": "내 피부 적합",
    "env_fit": "환경 적합",
    "value_signal": "가성비",
}


class ScoreItem(BaseModel):
    """점수 항목 하나. 화면의 점수 분해 한 줄이 된다."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)


class ScoredProduct(BaseModel):
    """Score 노드가 후보 하나에 대해 내놓는 값."""

    model_config = ConfigDict(extra="forbid")

    product_id: str
    total: int = Field(ge=0, le=100)
    breakdown: list[ScoreItem] = Field(default_factory=list)


class ScoreContext(BaseModel):
    """scorer 가 점수를 내는 데 필요한 것 전부.

    scorer 가 직접 state 를 읽지 않게 한다. 그래야 단위 테스트에서 이 객체만
    만들어 주면 되고, 노드 순서가 바뀌어도 scorer 는 영향을 받지 않는다.
    """

    model_config = ConfigDict(extra="forbid")

    # 리뷰 점수는 job 에 묶인 값을 읽는다. 이게 없으면 조용히 0점이 나온다.
    # 선택 값으로 두면 같은 사고가 반복되므로 필수로 받는다.
    job_id: str
    user_id: str
    query_spec: QuerySpec
    user_profile: dict[str, Any] = Field(default_factory=dict)
    inventory: list[dict[str, Any]] = Field(default_factory=list)
    env_summary: dict[str, Any] | None = None
    # 카테고리 평균가처럼 후보 하나만 봐서는 알 수 없는 값.
    category_stats: dict[str, Any] = Field(default_factory=dict)


class Scorer(Protocol):
    """scorers/ 에 두는 함수 하나의 모양.

    후보를 하나씩이 아니라 **한꺼번에** 받는다. 리뷰 일치도나 가성비는
    후보 하나만 봐서는 계산할 수 없고 코퍼스 통계가 필요한데, 하나씩 받으면
    후보 수만큼 조회가 나간다.

    반환은 {product_id: 0~100 또는 None} 이다. 빠진 product_id 는 None 으로
    본다. **None 은 0점이 아니다.** 0점은 "이 항목 기준으로 나쁜 제품"이고
    None 은 "이번 요청에서는 따지지 않는 항목"이라, None 인 항목은 가중치
    계산에서 통째로 빠진다. 환경을 따지지 않는 요청에서 env_fit 을 0점으로
    돌려주면 모든 후보가 환경 점수만큼 깎인다.
    """

    async def __call__(
        self, products: list[dict[str, Any]], ctx: ScoreContext
    ) -> dict[str, float | None]: ...


def build_score(
    product_id: str,
    scores: dict[str, float | None],
    weights: dict[str, float],
) -> ScoredProduct:
    """항목별 점수와 가중치를 합쳐 후보 하나의 최종 점수를 만든다.

    None 인 항목을 빼고 **남은 항목의 가중치를 다시 1로 맞춘다.** 이 재정규화가
    없으면 항목이 빠질 때마다 총점이 같이 내려가, 환경을 따지지 않는 요청의
    점수가 따지는 요청보다 항상 낮게 나온다.
    """
    쓸_항목 = {
        키: 값
        for 키, 값 in scores.items()
        if 값 is not None and weights.get(키, 0) > 0
    }
    가중치_합 = sum(weights[키] for 키 in 쓸_항목)
    if 가중치_합 <= 0:
        # 쓸 항목이 하나도 없다. 0점을 돌려주면 "나쁜 제품"으로 보여서
        # 설정 실수가 결과에 묻힌다. 빌더가 job 을 실패로 남기게 한다.
        raise ValueError(
            f"{product_id}: 점수를 낼 수 있는 항목이 없다 "
            f"(scores={scores}, weights={weights})"
        )

    breakdown: list[ScoreItem] = []
    총점 = 0.0
    for 키, 점수 in 쓸_항목.items():
        비중 = weights[키] / 가중치_합
        총점 += 점수 * 비중
        breakdown.append(
            ScoreItem(
                key=키,
                label=SCORE_LABELS.get(키, 키),
                score=점수,
                weight=round(비중, 4),
            )
        )

    breakdown.sort(key=lambda 항목: 항목.weight, reverse=True)
    return ScoredProduct(product_id=product_id, total=round(총점), breakdown=breakdown)
