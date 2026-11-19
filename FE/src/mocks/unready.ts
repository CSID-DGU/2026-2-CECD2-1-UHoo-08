/**
 * 아직 BE·AI 결과가 준비되지 않은 기능의 목데이터.
 *
 * VITE_MOCK_UNREADY=true 일 때만 쓴다. 대상은 다섯 가지다.
 * - 환경 요약(/environment/summary), 일별 추이(/environment/daily)
 * - 홈 환경 추천(/home/recommendations/environment) ← home_env.json
 * - 예산 세트 결과(S6) ← s6_bundle.json, 세트 교체 후보·교체(/bundles/...)
 *
 * home_env.json, s6_bundle.json 은 AI 내부 계약 모양이라, 화면이 받는 BE 응답 모양으로
 * 바꿔서 쓴다. 나머지는 BE 응답 스키마(Swagger)에 맞춰 만든 값이다. 숫자끼리 서로
 * 맞도록(예: "6 이상인 날이 22일" 과 막대 22개) 문구는 값에서 계산한다.
 *
 * 실제 데이터가 들어오면 플래그만 끄면 된다. 이 파일을 지워도 화면 코드는 그대로 동작한다.
 */
import type {
  EnvMetric,
  EnvironmentDaily,
  EnvironmentRecommendation,
  EnvironmentSummary,
} from "../api/homeApi";
import type {
  Bundle,
  BundleSlotOptions,
  QueryResult,
  ResultItem,
} from "../api/recommendationQueryApi";
import homeEnv from "./recommendationV2/home_env.json";
import s6Bundle from "./recommendationV2/s6_bundle.json";

export const MOCK_UNREADY = import.meta.env.VITE_MOCK_UNREADY === "true";

/** 목데이터로 만든 추천 job. 상세·피드백처럼 실제 서버가 필요한 동작을 막는 데 쓴다. */
export const isMockJob = (jobId: string | null | undefined) => Boolean(jobId?.startsWith("mock-"));

// ── 공통 ─────────────────────────────────────────────────────────────────

type AiItem = (typeof homeEnv.items)[number];

/** AI 계약의 결과 카드를 BE 응답 카드로. 목데이터의 이미지 주소는 가짜라 비운다. */
function toResultItem(item: AiItem): ResultItem {
  return {
    productId: item.productId,
    name: item.name,
    brand: item.brand,
    imageUrl: null,
    price: item.price,
    totalScore: item.totalScore,
    rating: null,
    reviewCount: null,
    breakdown: item.breakdown,
    badges: item.badges,
    reason: item.reason,
    change: null,
    rankDelta: null,
  };
}

function isoDate(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

/** 오늘을 마지막 날로 하는 최근 28일. 오래된 순 */
function lastDays(count = 28): string[] {
  const today = new Date();
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(today);
    day.setDate(today.getDate() - (count - 1 - index));
    return isoDate(day);
  });
}

// ── 환경 일별·요약 ───────────────────────────────────────────────────────

/**
 * 지표별 28일 값. 오래된 순.
 * 자외선 6 이상 22일, 미세먼지 80 초과 9일, 습도 40% 미만 12일(평균 38%)이 되도록 맞췄다.
 * null 은 관측이 없는 날이다.
 */
const SERIES: Record<EnvMetric, (number | null)[]> = {
  UV: [6, 7, 7, 5, 6, 8, 7, 6, 4, 6, 7, 7, 6, 5, 6, 8, 9, 7, 6, 6, 3, 6, 7, 6, 5, 6, 7, 5],
  PM: [42, 55, 88, 96, 61, 38, 47, 83, 102, 71, 52, 44, 39, 91, 86, 58, 49, 36, 64, 95, 81, 57, 43, 50, 84, 66, 41, null],
  HUMIDITY: [58, 54, 46, 45, 47, 44, 55, 52, 50, 44, 43, 24, 45, 47, 27, 25, 23, 26, 44, 46, 24, 22, 25, 27, 48, 26, 24, 23],
  TEMP: [14.2, 13.8, 12.9, 13.5, 12.1, 11.4, 11.9, 10.8, 10.2, 9.7, 9.9, 10.4, 9.1, 8.6, 8.9, 9.3, 8.2, 7.8, 8.4, 7.9, 7.1, 6.8, 7.4, 6.9, 6.2, 5.8, 6.5, 6.1],
};

const METRIC_INFO: Record<EnvMetric, { label: string; threshold: number | null; over: (v: number) => boolean }> = {
  UV: { label: "자외선 지수", threshold: 6, over: (v) => v >= 6 },
  PM: { label: "미세먼지", threshold: 80, over: (v) => v > 80 },
  HUMIDITY: { label: "습도", threshold: 40, over: (v) => v < 40 },
  TEMP: { label: "기온", threshold: null, over: () => false },
};

function countOver(metric: EnvMetric): number {
  return SERIES[metric].filter((v) => v != null && METRIC_INFO[metric].over(v)).length;
}

function average(metric: EnvMetric): number {
  const values = SERIES[metric].filter((v): v is number => v != null);
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

const percentOfMonth = (count: number) => Math.round((count / SERIES.UV.length) * 100);

export function mockEnvironmentDaily(metric: EnvMetric): EnvironmentDaily {
  const info = METRIC_INFO[metric];
  const dates = lastDays(SERIES[metric].length);
  const over = countOver(metric);
  const text: Record<EnvMetric, { headline: string; subText: string }> = {
    UV: { headline: `6 이상인 날이 ${over}일`, subText: `'높음' 구간이 한 달의 ${percentOfMonth(over)}%예요` },
    PM: { headline: `나쁨(80 초과)인 날이 ${over}일`, subText: `'나쁨' 구간이 한 달의 ${percentOfMonth(over)}%예요` },
    HUMIDITY: { headline: `40% 미만인 날이 ${over}일`, subText: `건조한 날이 한 달의 ${percentOfMonth(over)}%예요` },
    TEMP: { headline: `평균 ${average("TEMP").toFixed(1)}℃`, subText: "최근 4주 동안 조금씩 쌀쌀해졌어요" },
  };
  return {
    metric,
    label: info.label,
    headline: text[metric].headline,
    subText: text[metric].subText,
    threshold: info.threshold,
    days: SERIES[metric].map((value, index) => ({
      date: dates[index],
      value,
      exceeded: value != null && info.over(value),
    })),
  };
}

/** home_env.json 의 조건에, 일별 값에서 센 근거를 붙인다. */
function envConditions() {
  const basis: Record<string, string> = {
    UV_PROTECT: `자외선 지수 6 이상 ${countOver("UV")}일`,
    BARRIER: `습도 40% 미만 ${countOver("HUMIDITY")}일`,
    SOOTHING: `미세먼지 나쁨 ${countOver("PM")}일`,
  };
  return homeEnv.conditions.map((c) => ({ ...c, basis: basis[c.key] ?? c.basis }));
}

/** regionName 은 실제로 저장된 지역을 그대로 쓴다. 데이터 부분만 목데이터로 채운다. */
export function mockEnvironmentSummary(regionName: string): EnvironmentSummary {
  const dates = lastDays(SERIES.UV.length);
  const conditions = envConditions();
  return {
    regionName,
    periodStart: dates[0],
    periodEnd: dates[dates.length - 1],
    dayCount: dates.length,
    stats: {
      uvHighDays: countOver("UV"),
      dustBadDays: countOver("PM"),
      avgHumidity: Math.round(average("HUMIDITY")),
    },
    seasonChange: {
      title: "건조한 계절로 바뀌는 중이에요",
      message: "최근 7일 평균 습도가 3주 전보다 22%p 낮아졌어요. 보습을 한 단계 올려 보세요.",
    },
    recommendationAvailable: true,
    conditions,
    missingCount: conditions.filter((c) => !c.covered).length,
    updatedAt: new Date().toISOString(),
  };
}

// ── 홈 환경 추천 (home_env.json) ─────────────────────────────────────────

export function mockHomeEnvironmentRecommendation(): EnvironmentRecommendation {
  const conditions = envConditions();
  return {
    state: "READY",
    missingConditions: conditions.filter((c) => !c.covered).map(({ key, label }) => ({ key, label })),
    coveredConditions: conditions
      .filter((c) => c.covered)
      .map(({ key, label, coveredBy }) => ({ key, label, coveredBy })),
    result: {
      jobId: `mock-${homeEnv.jobId}`,
      parentJobId: null,
      scenario: homeEnv.scenario,
      basis: "SELF",
      summary: {
        categoryLabel: "스킨케어",
        totalCount: homeEnv.items.length,
        basisLabel: "요즘 환경 기준",
        conditions: homeEnv.query.conditions,
        notice: null,
      },
      appliedPreference: null,
      items: homeEnv.items.map(toResultItem),
      excluded: null,
      alternatives: [],
      alternativesDroppedCount: 0,
      similarUserProducts: [],
      bundles: [],
    },
    computedAt: new Date().toISOString(),
  };
}

// ── 예산 세트 (s6_bundle.json) ───────────────────────────────────────────

const BUDGET = s6Bundle.query.budgetTotal;

type AiBundleItem = (typeof s6Bundle.bundles)[number]["items"][number];

function toBundle(label: string, items: AiBundleItem[], index: number): Bundle {
  const total = items.reduce((sum, item) => sum + item.price, 0);
  return {
    index,
    type: null,
    label,
    total,
    remaining: BUDGET != null ? BUDGET - total : null,
    totalScore: Math.round(items.reduce((sum, item) => sum + item.totalScore, 0) / items.length),
    slots: items.map((item) => ({
      slotKey: item.slotKey,
      label: item.slotLabel,
      productId: item.productId,
      name: `${item.brand} ${item.name}`,
      price: item.price,
      score: item.totalScore,
    })),
  };
}

// 교체한 결과는 이 세션 동안 유지한다. 새로 검색하면 처음 조합으로 돌아간다.
let bundles: Bundle[] = [];

/** 예산 세트 검색 결과. AI 의 S6 단계가 생기기 전까지 이 값을 보여준다. */
export function mockBundleResult(): QueryResult {
  bundles = s6Bundle.bundles.map((b, i) => toBundle(b.label, b.items, i + 1));
  return {
    jobId: `mock-${s6Bundle.jobId}`,
    parentJobId: null,
    scenario: "S6_BUNDLE",
    basis: "SELF",
    summary: {
      categoryLabel: "스킨케어",
      totalCount: bundles.length,
      basisLabel: BUDGET != null ? `예산 ${BUDGET.toLocaleString("ko-KR")}원` : null,
      conditions: s6Bundle.query.conditions,
      notice: "예산 안에서 피부에 맞게 고른 조합이에요. 칸마다 다른 제품으로 바꿀 수 있어요.",
    },
    appliedPreference: null,
    items: [],
    excluded: null,
    alternatives: [],
    alternativesDroppedCount: 0,
    similarUserProducts: [],
    bundles: bundles.map((b) => ({ ...b, slots: [...b.slots] })),
  };
}

/** 한 칸에 넣을 수 있는 후보. 세 조합에 나온 같은 칸 제품들을 후보로 쓴다. */
export function mockBundleSlotOptions(bundleIndex: number, slotKey: string): BundleSlotOptions {
  const bundle = bundles.find((b) => b.index === bundleIndex);
  const current = bundle?.slots.find((s) => s.slotKey === slotKey);
  if (!bundle || !current) throw { error: { code: "NOT_FOUND", message: "세트나 칸이 없어요", status: 404 } };

  const seen = new Set<string>();
  const candidates = s6Bundle.bundles
    .flatMap((b) => b.items)
    .filter((item) => item.slotKey === slotKey && !seen.has(item.productId) && seen.add(item.productId));

  const rest = bundle.total - (current.price ?? 0);
  return {
    budget: BUDGET,
    currentTotal: bundle.total,
    options: candidates
      .map((item) => {
        const newTotal = rest + item.price;
        const remaining = BUDGET != null ? BUDGET - newTotal : null;
        return {
          productId: item.productId,
          name: `${item.brand} ${item.name}`,
          price: item.price,
          score: item.totalScore,
          newTotal,
          remaining,
          current: item.productId === current.productId,
          selectable: remaining == null || remaining >= 0,
          overBudgetBy: remaining != null && remaining < 0 ? -remaining : null,
        };
      })
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
  };
}

/** 칸을 바꾸고 합계·점수를 다시 계산한다. 예산을 넘으면 서버처럼 422 를 던진다. */
export function mockSwapBundle(bundleIndex: number, body: { slotKey: string; productId: string }): Bundle {
  const options = mockBundleSlotOptions(bundleIndex, body.slotKey);
  const picked = options.options.find((o) => o.productId === body.productId);
  if (!picked) throw { error: { code: "NOT_FOUND", message: "후보에 없는 제품이에요", status: 404 } };
  if (!picked.selectable)
    throw { error: { code: "BUNDLE_OVER_BUDGET", message: "예산을 넘어요", status: 422 } };

  bundles = bundles.map((bundle) => {
    if (bundle.index !== bundleIndex) return bundle;
    const slots = bundle.slots.map((slot) =>
      slot.slotKey === body.slotKey
        ? { ...slot, productId: picked.productId, name: picked.name, price: picked.price, score: picked.score }
        : slot,
    );
    const total = slots.reduce((sum, slot) => sum + (slot.price ?? 0), 0);
    return {
      ...bundle,
      slots,
      total,
      remaining: BUDGET != null ? BUDGET - total : null,
      totalScore: Math.round(slots.reduce((sum, slot) => sum + (slot.score ?? 0), 0) / slots.length),
    };
  });
  return bundles.find((b) => b.index === bundleIndex)!;
}
