import { Check } from "lucide-react";
import { MatchingAnimation } from "./MatchingAnimation";
import { RECOMMENDATION_STAGES, recommendationStageIndex } from "./recommendationStages";

/** 서버 상태 응답의 단계 한 줄(AI graph/registry.py 의 단계 이름) */
export interface AnalysisStep {
  key: string;
  label: string;
  state: "DONE" | "NOW" | "TODO";
}

interface AnalysisCopy {
  /** 페이지 머리말(추천 준비 중 페이지) */
  header: string;
  title: string;
  description: string;
  footnote: string;
}

/**
 * 시나리오별 문구. 상태 응답의 scenario 로 고른다. 판정 전(null)이면 요청을 이해하는 중이다.
 * 같은 로딩을 모든 요청에 보여주면 "이 제품 어때?"에도 "제품을 찾고 있어요"가 떠서 어긋난다.
 */
const COPY: Record<string, AnalysisCopy> = {
  S1_EVALUATE: {
    header: "적합도 분석 중",
    title: "이 제품이 내 피부에 맞는지 보고 있어요",
    description: "피부 정보, 후기, 가격을 함께 따져 점수를 매겨요",
    footnote: "분석이 끝나면 세부 점수와 대체 제품을 함께 보여드려요",
  },
  S2_SEARCH: {
    header: "제품 찾는 중",
    title: "조건에 맞는 제품을 고르고 있어요",
    description: "내 피부에 맞는 순서로 정리하고 있어요",
    footnote: "결과가 나오면 추천 이유와 함께 보여드려요",
  },
  S6_BUNDLE: {
    header: "세트 구성 중",
    title: "예산 안에서 세트를 짜고 있어요",
    description: "칸마다 어울리는 제품을 맞춰 보고 있어요",
    footnote: "조합마다 합계와 남는 예산을 같이 보여드려요",
  },
  S7_REFINE: {
    header: "다시 고르는 중",
    title: "바꾼 조건으로 다시 고르고 있어요",
    description: "더한 조건을 반영해 순위를 다시 매기고 있어요",
    footnote: "달라진 순위를 함께 표시해 드려요",
  },
};

const PENDING: AnalysisCopy = {
  header: "요청 확인 중",
  title: "요청을 이해하고 있어요",
  description: "질문에 맞는 방법을 고르고 있어요",
  footnote: "잠시만 기다려 주세요",
};

const OTHER: AnalysisCopy = {
  header: "분석 중",
  title: "AI가 분석하고 있어요",
  description: "필요한 정보를 모아 정리하고 있어요",
  footnote: "분석에 시간이 걸릴 수 있어요",
};

export function analysisCopy(scenario: string | null | undefined): AnalysisCopy {
  if (!scenario) return PENDING;
  return COPY[scenario] ?? OTHER;
}

/**
 * AI 추천·평가를 기다리는 화면. 검색 화면과 추천 준비 중 페이지가 같이 쓴다.
 *
 * 단계는 서버가 준 steps 를 그대로 그린다. 시나리오마다 거치는 단계가 달라(평가의 대체 제품 찾기,
 * 세트의 예산 나누기 등) FE 가 고정 목록에 끼워 맞추면 어긋난다. steps 가 없는 예전 형식 job 은
 * 단계 이름(step)을 고정 단계표에 맞춰 보여준다.
 */
export function AnalysisLoading({
  scenario,
  steps,
  step,
  progress,
  paused = false,
}: {
  scenario: string | null;
  steps: AnalysisStep[] | null;
  step: string | null;
  progress: number | null;
  paused?: boolean;
}) {
  const copy = analysisCopy(scenario);
  const list = Array.isArray(steps) && steps.length > 0 ? steps : null;

  // 지금 단계와 애니메이션 단계(찾기 → 분석 → 정리)
  let now: string | null;
  let ratio: number;
  if (list) {
    const index = list.findIndex((s) => s.state === "NOW");
    const done = list.filter((s) => s.state === "DONE").length;
    now = index >= 0 ? list[index].label : step;
    ratio = (index >= 0 ? index : done) / list.length;
  } else {
    const index = recommendationStageIndex(step ?? "");
    now = index >= 0 ? RECOMMENDATION_STAGES[index].label : step;
    ratio = index >= 0 ? index / RECOMMENDATION_STAGES.length : 0;
  }
  const phase = ratio < 0.34 ? "search" : ratio < 0.75 ? "analyze" : "compose";
  const percent =
    progress != null && Number.isFinite(progress)
      ? Math.round(Math.max(0, Math.min(100, progress)))
      : null;

  return (
    <section className="mt-6" aria-label={`${copy.header} 진행 상태`}>
      <div className="text-center">
        <MatchingAnimation phase={phase} paused={paused} />
        <h2 className="mt-4 text-h3 text-gray-500">{copy.title}</h2>
        <p className="mt-2 text-caption text-gray-300">{copy.description}</p>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between gap-3 text-xs">
          <span role="status" aria-live="polite" className="text-gray-400">
            {now || "분석 준비 중"}
          </span>
          <span className="font-semibold tabular-nums text-primary-600">
            {percent == null ? "" : `${percent}%`}
          </span>
        </div>
        <div
          role="progressbar"
          aria-label={`${copy.header} 진행률`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent ?? undefined}
          aria-valuetext={percent == null ? "서버 응답을 기다리고 있어요" : `${percent}%`}
          className="h-1.5 overflow-hidden rounded-full bg-gray-100"
        >
          <div
            className={`h-full rounded-full bg-primary-200 ${percent == null ? "search-progress-pending" : "w-full origin-left transition-transform duration-500 motion-reduce:transition-none"}`}
            style={percent == null ? { width: "28%" } : { transform: `scaleX(${percent / 100})` }}
          />
        </div>
      </div>

      {list && (
        <ol className="mt-5 grid gap-2" aria-label="진행 단계">
          {list.map((s) => (
            <li key={s.key} className="flex items-center gap-2.5 text-caption">
              <span
                aria-hidden="true"
                className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${
                  s.state === "DONE"
                    ? "bg-primary-100 text-primary-700"
                    : s.state === "NOW"
                      ? "border-2 border-primary-500"
                      : "border border-gray-200"
                }`}
              >
                {s.state === "DONE" && <Check className="h-3 w-3" strokeWidth={2.5} />}
                {s.state === "NOW" && <span className="h-1.5 w-1.5 rounded-full bg-primary-500" />}
              </span>
              <span
                className={
                  s.state === "NOW"
                    ? "font-semibold text-gray-500"
                    : s.state === "DONE"
                      ? "text-gray-400"
                      : "text-gray-300"
                }
              >
                {s.label}
                <span className="sr-only">
                  {s.state === "DONE" ? " 완료" : s.state === "NOW" ? " 진행 중" : " 대기"}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}

      <p className="mt-4 text-center text-[11px] leading-5 text-gray-300">{copy.footnote}</p>
    </section>
  );
}
