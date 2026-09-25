"""질의를 해석한 결과. Normalize 의 출력이자 Router 의 입력이다.

사용자 원문을 LLM에 바로 주고 시나리오를 고르게 하면, 같은 질문이 어떤 때는
A로 어떤 때는 B로 간다. 그래서 두 단계로 나눈다.

    Normalize  LLM이 빈칸을 채운다. 시나리오는 정하지 않는다.
    Router     채워진 값을 보고 코드가 고른다.

LLM이 흔들릴 수 있는 곳이 Normalize 한 곳으로 좁혀지고, 골든셋으로 측정할 수
있게 된다. 여기서 검증에 실패하면 1회 재시도하고, 그래도 안 되면 되묻는다.
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestType(str, Enum):
    """무엇을 해달라는 요청인가."""

    SEARCH = "SEARCH"      # 조건으로 찾아줘
    EVALUATE = "EVALUATE"  # 이 제품 어때? (+ 비슷한 거)
    BUNDLE = "BUNDLE"      # 이 예산으로 세트 짜줘
    REFINE = "REFINE"      # 방금 결과에 조건 추가


class Category(str, Enum):
    """상품 카테고리. 현재 DB에 들어 있는 값 그대로다."""

    BASE = "base"          # 쿠션, 파운데이션, 프라이머, 컨실러
    SUN = "sun"            # 선크림, 선스틱, 선쿠션, 선스프레이
    LIP = "lip"            # 틴트, 립스틱, 립글로스, 립밤
    SKINCARE = "skincare"  # 토너, 에센스, 세럼, 크림, 오일, 로션


class Target(str, Enum):
    """누구 기준으로 추천하나."""

    SELF = "SELF"        # 내 피부 기준
    POPULAR = "POPULAR"  # 전체 인기
    OTHER = "OTHER"      # 화면에서 입력한 다른 사람 조건


class Budget(BaseModel):
    """max 는 제품 하나의 상한, total 은 세트 전체의 상한이다.

    "3만원 이하 쿠션"은 max, "10만원으로 세트"는 total 이다. 둘을 한 필드로
    두면 세트 요청에서 제품 하나당 10만원으로 읽힌다.
    """

    model_config = ConfigDict(extra="forbid")

    max: int | None = Field(default=None, gt=0)
    total: int | None = Field(default=None, gt=0)


class BundleStep(BaseModel):
    """세트를 구성하는 단계 하나. "토너, 세럼, 크림" 의 각 항목."""

    model_config = ConfigDict(extra="forbid")

    category: Category | None = None
    product_type: str | None = None  # "토너", "세럼" 처럼 카테고리 안의 종류
    # 사용자가 쓴 표현 그대로. 화면에 그대로 보여준다.
    # 빈 값을 허용하면 무엇을 찾아야 하는지 모르는 단계가 세트에 들어가고,
    # bundle_steps 가 비어 있지 않다는 이유로 필수 필드 검사도 통과한다.
    label: str = Field(min_length=1)

    @field_validator("label")
    @classmethod
    def _공백_거부(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label 은 공백일 수 없다")
        return v


class QuerySpec(BaseModel):
    """Normalize 가 채우는 빈칸.

    쿼리에 없는 값을 추측해 채우지 않는다. 비어 있는 것과 잘못 채운 것 중
    잘못 채운 쪽이 훨씬 나쁘다. 비어 있으면 되물을 수 있지만, 잘못 채우면
    사용자가 요청하지 않은 조건으로 걸러진 결과가 나간다.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    request_type: RequestType

    # ── 무엇을 ────────────────────────────────────────────
    category: Category | None = None
    # EVALUATE 일 때 기준 상품. 상품 ID·상품명·URL 중 무엇이든 올 수 있어
    # 문자열로 받고, Discovery 가 실제 상품으로 해석한다.
    base_product_ref: str | None = None
    budget: Budget = Field(default_factory=Budget)
    bundle_steps: list[BundleStep] = Field(default_factory=list)

    # ── 어떤 조건으로 ─────────────────────────────────────
    # features 는 정규화된 조건이다. 필터로 바로 쓸 수 있다.
    #   {"finish": "세미매트", "lasting_power": "높음"}
    # conditions 는 정규화하지 못한 표현이다. 임베딩 검색 문장에 들어간다.
    #   ["여름 휴가용", "친구가 추천한"]
    # 둘을 한 곳에 담으면 필터에 쓸 수 있는 값과 아닌 값이 섞여,
    # Retrieve 가 매번 무엇이 필터 가능한지 다시 판단해야 한다.
    features: dict[str, Any] = Field(default_factory=dict)
    conditions: list[str] = Field(default_factory=list)
    exclude_ingredients: list[str] = Field(default_factory=list)

    # ── 어떻게 ────────────────────────────────────────────
    target: Target = Target.SELF
    use_env: bool = False       # "요즘 날씨에 맞는" → env_fit 점수 항목을 켠다
    value_seeking: bool = False  # "가성비" → value_signal 가중치를 올린다

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("conditions", "exclude_ingredients")
    @classmethod
    def _정리(cls, v: list[str]) -> list[str]:
        """공백을 털고 빈 값과 중복을 없앤다. 순서는 유지한다."""
        본 = set()
        결과 = []
        for 항목 in v:
            항목 = 항목.strip()
            if 항목 and 항목 not in 본:
                본.add(항목)
                결과.append(항목)
        return 결과

    def missing_required(self) -> tuple[str, ...]:
        """이 요청 유형에 필요한데 비어 있는 필드."""
        빠진 = []
        for 필드 in REQUIRED_FIELDS[self.request_type]:
            if 필드 == "budget.total":
                if self.budget.total is None:
                    빠진.append(필드)
            elif not getattr(self, 필드):
                빠진.append(필드)
        return tuple(빠진)


# 요청 유형별 필수 필드. 하나라도 비면 되묻는다.
#
# LLM에게 "빠진 게 뭔지도 같이 알려줘"라고 시키지 않고 코드로 계산한다.
# 값을 못 채운 모델이 무엇을 못 채웠는지는 정확히 아는 쪽이 이상하다.
REQUIRED_FIELDS: dict[RequestType, tuple[str, ...]] = {
    RequestType.SEARCH: (),
    RequestType.EVALUATE: ("base_product_ref",),
    RequestType.BUNDLE: ("budget.total", "bundle_steps"),
    # REFINE 의 parent_job_id 는 질의가 아니라 화면에서 온다. state 가 갖는다.
    RequestType.REFINE: (),
}

# 이 아래면 무엇을 물어야 할지 모르는 상태로 본다. 그대로 태우면
# 엉뚱한 시나리오로 가므로 되묻는다.
CONFIDENCE_THRESHOLD = 0.6


def needs_clarification(spec: QuerySpec) -> bool:
    """되물어야 하는 질의인가."""
    return bool(spec.missing_required()) or spec.confidence < CONFIDENCE_THRESHOLD
