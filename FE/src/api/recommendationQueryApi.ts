import { api } from "../lib/api";
import { isMockJob, mockBundleSlotOptions, mockSwapBundle } from "../mocks/unready";

/**
 * 자연어 추천(v2) API.
 *
 * 검색창 문장, 조건 추가, 되묻기 답변, 피드백이 모두 같은 job 흐름을 탄다.
 * 요청 → 상태 폴링 → 결과 조회 순서다.
 *
 * 응답 모양은 BE 의 RecommendationResultV2Response 와 같다.
 * `api/recommendationV2.ts` 는 AI 내부 계약(result.py)을 따른 타입이라 모양이 다르다.
 */

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export type RecommendationBasis = "SELF" | "POPULAR" | "OTHER";

export type JobStatus =
  | "PENDING"
  | "IN_PROGRESS"
  | "NEEDS_CLARIFICATION"
  | "COMPLETED"
  | "FAILED";

export type RefinePresetKey =
  | "CHEAPER"
  | "UNSCENTED"
  | "HIGH_COVERAGE"
  | "LONG_LASTING"
  | "UV_PROTECT"
  | "SENSITIVE_OK";

export type FeedbackReason = "TOO_EXPENSIVE" | "NOT_MY_SKIN" | "BAD_REVIEWS";

export type ClarifyInputType = "AMOUNT" | "TEXT_LIST" | "TEXT" | "PRODUCT";

/** 되묻기에서 물어보는 항목. key 는 답을 보낼 때의 키다. */
export interface ClarifyField {
  key: "budget" | "bundleSteps" | "category" | "baseProduct" | string;
  label: string;
  inputType: ClarifyInputType;
  presets: number[] | null;
}

export interface QueryStatus {
  jobId: string;
  status: JobStatus;
  step: string | null;
  progress: number | null;
  /** 판정 전이면 null */
  scenario: string | null;
  steps: { key: string; label: string; state: "DONE" | "NOW" | "TODO" }[] | null;
  /** NEEDS_CLARIFICATION 일 때만 */
  clarify: { message: string; fields: ClarifyField[] } | null;
}

export interface ResultItem {
  productId: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  /** 0~100. 인기 기준이면 null */
  totalScore: number | null;
  rating: number | null;
  reviewCount: number | null;
  breakdown: { key: string; label: string; score: number; weight: number }[] | null;
  badges: { type: string; text: string }[] | null;
  reason: string | null;
  /** 조건 수정 결과에서만. NEW, SAME, UP, DOWN */
  change: "NEW" | "SAME" | "UP" | "DOWN" | null;
  rankDelta: number | null;
}

export interface QueryResult {
  jobId: string;
  parentJobId: string | null;
  scenario: string;
  basis: RecommendationBasis;
  summary: {
    categoryLabel: string | null;
    totalCount: number;
    basisLabel: string | null;
    conditions: string[];
    notice: string | null;
  } | null;
  appliedPreference: { text: string; changeId: string | null } | null;
  items: ResultItem[];
  excluded: {
    count: number;
    items: { productId: string; name: string | null; reason: string; detail: string | null }[];
  } | null;
  /** 상품 평가·조건 수정의 비슷한 대체 상품. 이미지는 BE 가 내려주지 않는다 */
  alternatives: AlternativeItem[] | null;
  /** 점수 기준 미달로 뺀 대체 후보 수 */
  alternativesDroppedCount: number;
  /** 피부 타입·고민이 비슷한 사람들이 쓰는 제품. 이미지는 BE 가 내려주지 않는다 */
  similarUserProducts: SimilarUserProduct[] | null;
  /** 예산 세트(S6) 조합. 다른 시나리오에서는 빈 배열 */
  bundles: Bundle[] | null;
}

/** 예산 세트 조합 하나 (BE RecommendationResultV2Response.Bundle) */
export interface Bundle {
  /** 1부터 */
  index: number;
  type: string | null;
  /** "균형형", "알뜰형" 같은 성격 이름 */
  label: string;
  total: number;
  /** 예산 - 합계. 예산이 없으면 null, 넘었으면 음수 */
  remaining: number | null;
  totalScore: number;
  slots: BundleSlot[];
}

export interface BundleSlot {
  slotKey: string;
  /** "토너", "세럼" 같은 칸 이름 */
  label: string | null;
  productId: string;
  name: string;
  price: number | null;
  score: number | null;
}

/** 세트의 한 칸을 바꿀 때 고를 수 있는 후보 (BE BundleSlotOptionsResponse) */
export interface BundleSlotOptions {
  budget: number | null;
  currentTotal: number;
  options: {
    productId: string;
    name: string;
    price: number;
    score: number | null;
    /** 이 후보로 바꿨을 때의 합계 */
    newTotal: number;
    remaining: number | null;
    /** 지금 들어 있는 제품. BE 는 isCurrent 로 보낸다(BundleSlotOptionsResponse.Option) */
    isCurrent: boolean;
    /** 예산 안이면 true */
    selectable: boolean;
    overBudgetBy: number | null;
  }[];
}

export interface AlternativeItem {
  productId: string;
  name: string;
  brand: string;
  price: number | null;
  /** 0~1. AI 가 점수에 유사도를 넣었을 때만 */
  similarity: number | null;
  totalScore: number | null;
}

export interface SimilarUserProduct {
  productId: string;
  name: string;
  brand: string;
  price: number | null;
}

export interface RefinementOptions {
  currentConditions: string[];
  presets: { key: RefinePresetKey; label: string; frequent: boolean }[];
}

export interface RefinementHistoryStep {
  jobId: string;
  label: string;
  detail: string;
  candidateCount: number;
  isCurrent: boolean;
}

export const requestQuery = (body: {
  query?: string;
  baseProductId?: string;
  basis?: RecommendationBasis;
}) =>
  api.post<ApiResponse<{ jobId: string; estimatedSeconds: number; statusUrl: string }>>(
    "/recommendations/queries",
    body,
  );

export const getQueryStatus = (jobId: string) =>
  api.get<ApiResponse<QueryStatus>>(`/recommendations/${jobId}/status`);

export const getQueryResult = (jobId: string) =>
  api.get<ApiResponse<QueryResult>>(`/recommendations/${jobId}`);

export const answerClarification = (
  jobId: string,
  answers: {
    budget?: number;
    bundleSteps?: string[];
    category?: string;
    baseProduct?: string;
    text?: string;
  },
) =>
  api.post<ApiResponse<{ jobId: string; status: JobStatus }>>(
    `/recommendations/${jobId}/clarifications`,
    { answers },
  );

export const getRefinementOptions = (jobId: string) =>
  api.get<ApiResponse<RefinementOptions>>(`/recommendations/${jobId}/refinement-options`);

export const requestRefinement = (
  jobId: string,
  body: { presetKeys?: RefinePresetKey[]; freeText?: string },
) =>
  api.post<ApiResponse<{ jobId: string; parentJobId: string; estimatedSeconds: number }>>(
    `/recommendations/${jobId}/refinements`,
    body,
  );

export const getRefinementHistory = (jobId: string) =>
  api.get<ApiResponse<{ steps: RefinementHistoryStep[] }>>(
    `/recommendations/${jobId}/refinements/history`,
  );

export const submitFeedback = (
  jobId: string,
  body: { productId: string; vote: "UP" | "DOWN"; reasonTags?: FeedbackReason[] },
) =>
  api.post<ApiResponse<{ feedbackId: string; message: string; changeId: string | null }>>(
    `/recommendations/${jobId}/feedback`,
    body,
  );

/**
 * 피드백이나 자주 고른 조건으로 바뀐 가중치 한 건을 되돌린다.
 * 이미 되돌렸으면 409 CHANGE_NOT_REVERTIBLE, 내 변경이 아니면 404 NOT_FOUND.
 */
export const revertPreferenceChange = (changeId: string) =>
  api.post<ApiResponse<{ changeId: string; reverted: boolean }>>(
    `/users/me/preference-weights/changes/${encodeURIComponent(changeId)}/revert`,
  );

/** 세트 한 칸의 교체 후보. 목데이터 세트(jobId 가 mock- 으로 시작)면 목데이터로 답한다. */
export const getBundleSlotOptions = async (jobId: string, bundleIndex: number, slotKey: string) => {
  if (isMockJob(jobId)) return { success: true, data: mockBundleSlotOptions(bundleIndex, slotKey) };
  return api.get<ApiResponse<BundleSlotOptions>>(
    `/recommendations/${jobId}/bundles/${bundleIndex}/slots/${encodeURIComponent(slotKey)}/options`,
  );
};

/** 세트 한 칸을 고른 제품으로 바꾼다. 예산을 넘으면 서버가 422 BUNDLE_OVER_BUDGET */
export const swapBundleProduct = async (
  jobId: string,
  bundleIndex: number,
  body: { slotKey: string; productId: string },
) => {
  if (isMockJob(jobId)) return { success: true, data: { bundle: mockSwapBundle(bundleIndex, body) } };
  return api.patch<ApiResponse<{ bundle: Bundle }>>(`/recommendations/${jobId}/bundles/${bundleIndex}`, body);
};

/** 서버 오류 본문에서 코드와 문구를 꺼낸다. 모양이 달라도 터지지 않게 한다. */
export function apiErrorCode(error: unknown): string | null {
  if (error && typeof error === "object") {
    const e = error as { code?: unknown; error?: { code?: unknown } };
    if (typeof e.code === "string") return e.code;
    if (typeof e.error?.code === "string") return e.error.code;
  }
  return null;
}
