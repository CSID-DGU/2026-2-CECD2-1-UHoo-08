"""추천 결과. Compose 의 출력이고, BE 가 저장하는 값이고, FE 가 그리는 값이다.

셋이 같은 모양이어야 해서 여기 한 곳에서 정의한다. 필드 이름은 화면 쪽
관례를 따라 camelCase 로 직렬화한다(`model_dump(by_alias=True)`).
파이썬 쪽에서는 그대로 snake_case 로 쓴다.

QuerySpec 전체는 싣지 않는다. BE 가 `recommendation_jobs.query_spec` 컬럼에
따로 저장하므로, 여기에는 화면이 실제로 그리는 요약만 담는다. 내부 계약이
화면 응답으로 새어 나가면 계약을 고칠 때마다 FE가 깨진다.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from contracts.query_spec import Category, Target
from contracts.score import ScoreItem


class CamelModel(BaseModel):
    """FE로 나가는 모델의 공통 설정."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # 파이썬 쪽에서는 snake_case 로 만든다
        extra="forbid",
    )


class BadgeType(str, Enum):
    """카드에 붙는 한 줄짜리 표시."""

    CONFLICT_SEPARATE = "CONFLICT_SEPARATE"  # 보유 제품과 시간대를 나눠 쓰라는 안내
    ENV = "ENV"                              # 요즘 환경에 맞는 이유
    VALUE = "VALUE"                          # 가성비 근거
    TREND = "TREND"                          # 요즘 언급이 늘고 있다


class ExcludeReason(str, Enum):
    OWNED = "OWNED"        # 이미 쓰고 있다
    CONFLICT = "CONFLICT"  # 보유 제품과 함께 쓰지 않는 게 낫다


class RankChange(str, Enum):
    """조건 수정 전후 비교. 수정 결과 화면에서만 채운다."""

    NEW = "NEW"
    SAME = "SAME"
    UP = "UP"
    DOWN = "DOWN"


class Badge(CamelModel):
    type: BadgeType
    text: str = Field(min_length=1)


class ResultItem(CamelModel):
    """결과 카드 하나."""

    product_id: str = Field(min_length=1)
    name: str
    brand: str
    image_url: str | None = None
    price: int | None = None

    total_score: int = Field(ge=0, le=100)
    # 고정 키가 아니라 리스트다. 점수 항목이 늘어도 FE를 고치지 않는다.
    breakdown: list[ScoreItem] = Field(default_factory=list)

    badges: list[Badge] = Field(default_factory=list)
    reason: str | None = None

    # 조건 수정 결과에서만 채운다. 평소에는 None 이다.
    change: RankChange | None = None
    rank_delta: int | None = None


class ExcludedItem(CamelModel):
    """걸러낸 후보. 버리지 않고 사유와 함께 남긴다.

    "보유 제품과 충돌해 3개 제외" 처럼 보여줘야 사용자가 결과를 납득한다.
    """

    product_id: str = Field(min_length=1)
    name: str | None = None
    reason: ExcludeReason
    detail: str | None = None


class BundleOption(CamelModel):
    """예산 세트 조합 하나."""

    label: str = Field(min_length=1)  # "균형형", "알뜰형" 같은 성격 이름
    total_price: int = Field(ge=0)
    items: list[ResultItem] = Field(min_length=1)
    # 예산을 넘겼다면 왜 넘겼는지. 넘기지 않았으면 None.
    over_budget_reason: str | None = None


class Clarify(CamelModel):
    """되물을 내용. 채워져 있으면 job 이 NEEDS_CLARIFICATION 으로 멈춘 상태다."""

    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)  # 고르기 쉽게 주는 보기


class QuerySummary(CamelModel):
    """화면에 보여줄 만큼의 질의 요약.

    조건 수정 화면이 "지금 걸린 조건"을 그리는 데 쓴다.
    """

    raw: str = ""
    category: Category | None = None
    # features 와 conditions 를 사람이 읽는 문장으로 합친 것. "세미매트", "여름"
    conditions: list[str] = Field(default_factory=list)
    budget_max: int | None = None
    budget_total: int | None = None
    target: Target = Target.SELF
    use_env: bool = False
    value_seeking: bool = False


class RecommendationResult(CamelModel):
    """job 하나의 최종 결과."""

    job_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    query: QuerySummary = Field(default_factory=QuerySummary)

    items: list[ResultItem] = Field(default_factory=list)
    alternatives: list[ResultItem] = Field(default_factory=list)
    similar_user_products: list[ResultItem] = Field(default_factory=list)
    bundles: list[BundleOption] = Field(default_factory=list)
    excluded: list[ExcludedItem] = Field(default_factory=list)

    clarify: Clarify | None = None
