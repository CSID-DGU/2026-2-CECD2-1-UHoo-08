import { MatchingAnimation } from "../recommendation/MatchingAnimation";
import { RECOMMENDATION_STAGES, recommendationStageIndex } from "../recommendation/recommendationStages";

export function SearchAnalysisLoading({ searching, step, progress }: { searching: boolean; step: string; progress: number | null }) {
  const serverStage = recommendationStageIndex(step);
  const current = searching
    ? { label: "제품을 찾고 있어요", description: step }
    : RECOMMENDATION_STAGES[serverStage];
  const percent = !searching && progress != null && Number.isFinite(progress) ? Math.round(Math.max(0, Math.min(100, progress))) : null;
  return <section className="mt-6" aria-label="검색과 피부 분석 진행 상태">
    <div className="text-center" role="status" aria-live="polite">
      <MatchingAnimation phase={searching ? "search" : serverStage === 5 ? "compose" : "analyze"} />
      <h2 className="mt-4 text-h3 text-gray-500">{searching ? "제품을 찾고 있어요" : "AI가 제품을 분석하고 있어요"}</h2>
      <p className="mt-2 text-caption text-gray-300">{current?.description ?? step}</p>
    </div>
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between gap-3 text-xs">
        <span role="status" aria-live="polite" className="text-gray-300">{searching ? "요청에 맞는 제품 검색 중" : current?.label ?? step ?? "분석 준비 중"}</span>
        <span className="font-semibold tabular-nums text-primary-600">{percent == null ? "—%" : `${percent}%`}</span>
      </div>
      <div role="progressbar" aria-label={searching ? "검색 진행률" : "피부 분석 진행률"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined} aria-valuetext={percent == null ? "서버 응답을 기다리고 있어요" : `${percent}%`} className="h-1.5 overflow-hidden rounded-full bg-gray-100">
        <div className={`h-full rounded-full bg-[#9DBDE9] ${percent == null ? "search-progress-pending" : "transition-[width] duration-500 motion-reduce:transition-none"}`} style={{ width: percent == null ? "28%" : `${percent}%` }} />
      </div>
    </div>
    <p className="mt-4 text-center text-[11px] leading-5 text-gray-300">{searching ? "검색 결과를 준비하고 있어요" : "분석이 끝나면 제품과 분석 이유를 함께 보여드려요"}</p>
  </section>;
}
