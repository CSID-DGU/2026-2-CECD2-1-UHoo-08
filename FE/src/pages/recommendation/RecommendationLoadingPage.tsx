import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getRecommendationStatus } from "../../api/recommendationApi";
import { forgetAnalysisJob, validateAnalysisStatus, withDeadline } from "../../lib/searchAnalysis";
import { PageHeader } from "../../components/common/PageHeader";
import { SearchField } from "../../components/common/SearchField";
import AppLayout from "../../layouts/AppLayout";
import { MatchingAnimation } from "../../components/recommendation/MatchingAnimation";

import { RECOMMENDATION_STAGES as STEPS } from "../../components/recommendation/recommendationStages";

export function RecommendationLoadingPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { jobId?: string; query?: string; productName?: string; productId?: string } | null };
  const jobId = state?.jobId;
  const [progress, setProgress] = useState<number | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [label, setLabel] = useState("추천을 준비하고 있어요");
  const [notice, setNotice] = useState("");
  const [pollAttempt, setPollAttempt] = useState(0);
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    setEnded(false);
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = Date.now() + 180_000;
    async function poll() {
      try {
        if (Date.now() >= deadline) {
          setNotice("분석이 예상보다 오래 걸리고 있어요. 잠시 후 상태를 다시 확인해주세요.");
          return;
        }
        const response = await withDeadline(getRecommendationStatus(jobId!), Math.min(15_000, deadline - Date.now()));
        if (stopped) return;
        const data = validateAnalysisStatus(response.data);
        setNotice("");
        setProgress(data.progress == null ? null : Math.min(100, Math.max(0, data.progress)));
        setActiveIndex(STEPS.findIndex(step => step.keys.includes(data.step ?? "")));
        setLabel(data.step || "추천을 준비하고 있어요");
        if (data.status === "COMPLETED") { navigate("/recommendation/result", { state: { jobId }, replace: true }); return; }
        if (data.status === "FAILED" || data.status === "NEEDS_CLARIFICATION") {
          forgetAnalysisJob(jobId!);
          setEnded(true);
          if (data.status === "FAILED") setNotice("추천 분석에 실패했어요. 이전 화면에서 다시 시도해주세요.");
          else { setActiveIndex(-1); setLabel("추가 정보가 필요해요"); setNotice("추가 질문 화면은 아직 연결되지 않았어요. 이전 화면에서 요청을 수정해주세요."); }
          return;
        }
      } catch {
        if (stopped) return;
        setNotice("진행 상태를 불러오지 못했어요. 상태를 다시 확인해주세요.");
        return;
      }
      if (!stopped) timer = setTimeout(poll, 1000);
    }
    void poll();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
  }, [jobId, navigate, pollAttempt]);

  const current = STEPS[activeIndex];
  return (
    <AppLayout>
      <section className="px-5 pb-8 pt-10">
        <PageHeader title="추천 준비 중" onBack={() => navigate(-1)} />
        <div className="mt-5"><SearchField variant="outlined" value={state?.query ?? state?.productName ?? "맞춤 화장품 추천"} /></div>
        <div className="mt-6 text-center" role="status" aria-live="polite">
          <MatchingAnimation phase={activeIndex >= 5 ? "compose" : activeIndex >= 3 ? "analyze" : "search"} paused={Boolean(notice) || !jobId} />
          <h2 className="mt-5 text-h3 text-gray-500">AI가 제품을 분석하고 있어요</h2>
          <p className="mt-2 text-caption text-gray-300">{current?.description ?? "진행 상태를 확인하고 있어요"}</p>
        </div>
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span role="status" aria-live="polite" className="text-gray-300">{current?.label ?? label}</span><span className="font-semibold tabular-nums text-primary-600">{progress == null ? "—%" : `${Math.round(progress)}%`}</span></div>
          <div role="progressbar" aria-label="추천 진행률" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress ?? undefined} className="h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div className="h-full rounded-full bg-primary-500 transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${progress ?? 0}%` }} />
          </div>
        </div>
        {notice && <p role="status" className="mt-3 text-center text-caption text-gray-400">{notice}</p>}
        {notice && jobId && !ended && <button type="button" onClick={() => { setNotice(""); setPollAttempt(value => value + 1); }} className="mt-3 min-h-10 w-full text-caption font-semibold text-primary-600">분석 상태 다시 확인</button>}
        {notice && ended && <button type="button" onClick={() => navigate(-1)} className="mt-3 min-h-10 w-full text-caption font-semibold text-primary-600">이전 화면으로 돌아가기</button>}
        {!jobId && <p className="mt-3 text-center text-caption text-gray-300">추천 요청 정보가 없어요. 이전 화면에서 추천을 시작해주세요.</p>}
        <p className="mt-3 text-center text-[11px] text-gray-300">분석에 시간이 걸릴 수 있어요</p>
      </section>
    </AppLayout>
  );
}
