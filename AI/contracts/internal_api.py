"""BE 가 AI 를 부를 때 주고받는 값.

BE 는 이 모양에 맞춰 호출부를 먼저 만들고, AI 는 내용을 나중에 채운다.
둘이 같은 파일을 보지 않으면 필드 이름이 하나만 달라도 조용히 무시된다.
`docs/internal-api.md` 에 같은 내용을 표로 정리해 두었다.

필드 이름은 BE·FE 관례를 따라 camelCase 다. 그래프 안쪽에서만 snake_case 를
쓴다(graph/state.py).
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from contracts.query_spec import Target
from contracts.result import CompatibilityLevel


class WireModel(BaseModel):
    """BE 와 주고받는 모델의 공통 설정."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class JobStatus(str, Enum):
    """추천 job 의 상태.

    PENDING → IN_PROGRESS → (NEEDS_CLARIFICATION) → COMPLETED | FAILED

    NEEDS_CLARIFICATION 은 되묻는 중이라 사용자의 답을 기다리는 상태다.
    실패가 아니므로 BE 는 이 상태에서 job 을 정리하지 않는다.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HomeKind(str, Enum):
    ROUTINE = "ROUTINE"  # 보유 제품끼리의 성분 충돌 점검
    ENV = "ENV"          # 4주 환경에 견줘 부족한 기능 보완


class Accepted(WireModel):
    """비동기 엔드포인트의 응답.

    결과는 이 응답이 아니라 DB(recommendation_jobs, home_recommendations)로
    간다. BE 는 job 을 조회해 진행 상태를 본다.
    """

    accepted: bool = True
    job_id: str | None = None
    # 아직 내용이 없는 경로다. 응답만 보고 구현된 것으로 오해하면
    # 빈 결과를 정상으로 읽게 되므로 표시를 남긴다.
    stub: bool = False


# ── POST /internal/agent/run/v2 ───────────────────────────────
class AgentRunV2Request(WireModel):
    """추천 실행 요청. 질의와 기준 상품 중 하나는 있어야 한다.

    기준 상품이 있으면 무엇을 평가할지 이미 아는 요청이다. 문장을 해석하지
    않고 평가 경로로 바로 간다. 질의가 함께 와도 조건으로 읽지 않는다.
    """

    job_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    raw_query: str | None = Field(default=None, min_length=1)
    base_product_id: str | None = Field(default=None, min_length=1)
    # 추천 기준. OTHER 면 target_profile 이 함께 온다.
    basis: Target = Target.SELF
    target_profile: dict | None = None
    # 조건 수정이면 직전 job. 그 job 의 스냅샷에서 조건과 후보를 복원한다.
    parent_job_id: str | None = None

    @model_validator(mode="after")
    def _질의나_기준_상품이_있다(self) -> "AgentRunV2Request":
        if self.raw_query is None and self.base_product_id is None:
            raise ValueError("rawQuery 와 baseProductId 중 하나는 있어야 한다")
        return self

    @model_validator(mode="after")
    def _기준_상품과_이전_job_은_함께_오지_않는다(self) -> "AgentRunV2Request":
        # 기준 상품이 있으면 관문을 건너뛰어 조건 수정 경로로 갈 수 없다.
        # 이전 job 의 조건이 조용히 버려지지 않게 요청에서 막는다.
        if self.base_product_id is not None and self.parent_job_id is not None:
            raise ValueError("baseProductId 와 parentJobId 는 함께 보낼 수 없다")
        return self


# ── POST /internal/agent/clarify ──────────────────────────────
class AgentClarifyRequest(WireModel):
    job_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)


# ── POST /internal/products/recognize-photos ──────────────────
class RecognizePhotosRequest(WireModel):
    """제품명 면과 기한 면 사진. 둘 중 하나는 있어야 한다.

    기한 면만 나중에 찍으면 제품명 면을 보내지 않는다. 함께 보내면 이미 읽은
    제품명을 한 번 더 읽게 된다.
    """

    # 업로드된 이미지 URL
    name_image: str | None = Field(default=None, min_length=1)
    date_image: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _사진이_하나는_있다(self) -> "RecognizePhotosRequest":
        if self.name_image is None and self.date_image is None:
            raise ValueError("nameImage 와 dateImage 중 하나는 있어야 한다")
        return self


class ProductCandidate(WireModel):
    product_id: str
    name: str
    brand: str
    image_url: str | None = None
    confidence: float = Field(ge=0, le=1)


class RecognizePhotosResponse(WireModel):
    """인식 결과.

    읽지 못한 값은 비워 둔다. 추측해서 채우면 사용자가 그 값을 확인하지 않고
    넘기게 되고, 잘못된 기한이 소진 알림으로 이어진다.
    """

    candidates: list[ProductCandidate] = Field(default_factory=list)
    expiry_date: str | None = None   # YYYY-MM-DD
    pao_months: int | None = None    # 12M 같은 기호에서 읽은 값
    mfg_date: str | None = None
    # 인식 원본. user_products.recognized_raw 에 그대로 저장해
    # 사용자가 고친 최종값과 비교한다. 인식 정확도의 근거가 된다.
    raw: dict = Field(default_factory=dict)
    stub: bool = False


# ── POST /internal/home/run ───────────────────────────────────
class HomeRunRequest(WireModel):
    user_id: str = Field(min_length=1)
    kind: HomeKind


# ── POST /internal/compatibility/check ────────────────────────
class CompatibilityCheckRequest(WireModel):
    user_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)


class CompatibilityPairDetail(WireModel):
    """보유 제품 하나와 이 제품 사이에서 걸린 성분 조합."""

    user_product_id: str = Field(min_length=1)
    ingredient_a: str = Field(min_length=1)
    ingredient_b: str = Field(min_length=1)
    level: CompatibilityLevel
    advice: str | None = None
    schedule: str | None = None  # 시간대 안내 문구


class CompatibilityCheckResponse(WireModel):
    """쌍 중 가장 강한 단계가 level 이다.

    stub 이면 level 의 OK 는 판정 결과가 아니다. 괜찮다는 뜻으로 읽으면 안 된다.
    """

    level: CompatibilityLevel
    pairs: list[CompatibilityPairDetail] = Field(default_factory=list)
    stub: bool = False


# ── POST /internal/feedback/apply ─────────────────────────────
class FeedbackApplyRequest(WireModel):
    """이 사용자의 가중치 prior 를 다시 계산한다.

    피드백 한 건마다 부르지 않는다. 피드백은 BE 가 저장하고, 이 호출은
    저장 뒤에 한 번 던져 재계산만 시킨다.
    """

    user_id: str = Field(min_length=1)
