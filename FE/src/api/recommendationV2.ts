/**
 * 추천 결과 v2 응답 타입.
 *
 * AI 의 `AI/contracts/result.py` 와 같은 모양이다. 한쪽만 고치면 화면이 빈칸을
 * 그리므로, 필드를 바꿀 때는 두 파일을 같이 고친다.
 *
 * 프로젝트 tsconfig 가 `erasableSyntaxOnly` 라 enum 대신 문자열 유니온을 쓴다.
 */

export type Scenario =
  | "S1_EVALUATE"
  | "S2_SEARCH"
  | "S6_BUNDLE"
  | "S7_REFINE"
  | "HOME_ROUTINE"
  | "HOME_ENV"
  | "S4_REPLENISH";

export type Category = "base" | "sun" | "lip" | "skincare";

/** 누구 기준으로 추천했는지. */
export type Target = "SELF" | "POPULAR" | "OTHER";

export type BadgeType =
  /** 보유 제품과 시간대를 나눠 쓰라는 안내 */
  | "CONFLICT_SEPARATE"
  /** 요즘 환경에 맞는 이유 */
  | "ENV"
  /** 가성비 근거 */
  | "VALUE"
  /** 요즘 언급이 늘고 있다 */
  | "TREND";

export type ExcludeReason = "OWNED" | "CONFLICT";

/** 조건 수정 전후 비교. 수정 결과 화면에서만 채워진다. */
export type RankChange = "NEW" | "SAME" | "UP" | "DOWN";

/**
 * 점수 항목 하나.
 *
 * 고정 키가 아니라 배열이다. 항목이 늘어도 화면은 이 배열을 그대로 그리면 된다.
 * `key` 는 `budget_fit` 처럼 snake_case 인데, 필드 이름이 아니라 AI 쪽 점수
 * 함수의 이름을 가리키는 값이라 그대로 둔다. 화면에는 `label` 을 쓴다.
 */
export interface ScoreItem {
  key: string;
  label: string;
  /** 0~100 */
  score: number;
  /** 0~1. 항목들의 합은 1이다. */
  weight: number;
}

export interface Badge {
  type: BadgeType;
  text: string;
}

/** 결과 카드 하나. */
export interface ResultItem {
  productId: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  /** 0~100 */
  totalScore: number;
  breakdown: ScoreItem[];
  badges: Badge[];
  reason: string | null;
  change: RankChange | null;
  rankDelta: number | null;
}

/** 걸러낸 후보. "보유 제품과 충돌해 N개 제외" 문구에 쓴다. */
export interface ExcludedItem {
  productId: string;
  name: string | null;
  reason: ExcludeReason;
  detail: string | null;
}

/** 예산 세트 조합 하나. */
export interface BundleOption {
  /** "균형형", "알뜰형" 같은 성격 이름 */
  label: string;
  totalPrice: number;
  items: ResultItem[];
  /** 예산을 넘겼을 때만 채워진다. */
  overBudgetReason: string | null;
}

/** 채워져 있으면 job 이 되묻기 상태로 멈춰 있다. */
export interface Clarify {
  question: string;
  options: string[];
}

/** 조건 수정 화면이 "지금 걸린 조건"을 그리는 데 쓴다. */
export interface QuerySummary {
  raw: string;
  category: Category | null;
  conditions: string[];
  budgetMax: number | null;
  budgetTotal: number | null;
  target: Target;
  useEnv: boolean;
  valueSeeking: boolean;
}

/** job 하나의 최종 결과. */
export interface RecommendationResult {
  jobId: string;
  scenario: Scenario;
  query: QuerySummary;
  items: ResultItem[];
  alternatives: ResultItem[];
  similarUserProducts: ResultItem[];
  bundles: BundleOption[];
  excluded: ExcludedItem[];
  clarify: Clarify | null;
}
