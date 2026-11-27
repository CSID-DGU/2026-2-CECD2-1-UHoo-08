/**
 * 아직 BE·AI 결과가 준비되지 않은 기능의 목데이터.
 *
 * VITE_MOCK_UNREADY=true 일 때만 쓴다. 대상은 예산 세트 하나다.
 * - 예산 세트 결과(S6) ← s6_bundle.json, 세트 교체 후보·교체(/bundles/...)
 *
 * 환경 요약 · 일별 추이 · 홈 환경 추천은 실제 데이터(환경 수집 · EnvHistory)가 들어와
 * 목데이터를 뗐다.
 *
 * s6_bundle.json 은 AI 내부 계약 모양이라, 화면이 받는 BE 응답 모양으로 바꿔서 쓴다.
 *
 * 실제 데이터가 들어오면 플래그만 끄면 된다. 이 파일을 지워도 화면 코드는 그대로 동작한다.
 */
import type { Bundle, BundleSlotOptions, QueryResult } from "../api/recommendationQueryApi";
import s6Bundle from "./recommendationV2/s6_bundle.json";

export const MOCK_UNREADY = import.meta.env.VITE_MOCK_UNREADY === "true";

/** 목데이터로 만든 추천 job. 상세·피드백처럼 실제 서버가 필요한 동작을 막는 데 쓴다. */
export const isMockJob = (jobId: string | null | undefined) => Boolean(jobId?.startsWith("mock-"));

// ── 공통 ─────────────────────────────────────────────────────────────────

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
    // 세트 점수는 칸 점수의 합이다(BE ResultAssembler.bundles 와 같게). 화면은 칸 점수와 합을 함께 보여 준다
    totalScore: items.reduce((sum, item) => sum + item.totalScore, 0),
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
      totalScore: slots.reduce((sum, slot) => sum + (slot.score ?? 0), 0),
    };
  });
  return bundles.find((b) => b.index === bundleIndex)!;
}
