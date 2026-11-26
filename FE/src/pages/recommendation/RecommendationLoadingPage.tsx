import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getQueryStatus } from "../../api/recommendationQueryApi";
import { forgetAnalysisJob, validateAnalysisStatus, withDeadline } from "../../lib/searchAnalysis";
import { PageHeader } from "../../components/common/PageHeader";
import { SearchField } from "../../components/common/SearchField";
import AppLayout from "../../layouts/AppLayout";
import { AnalysisLoading, analysisCopy, type AnalysisStep } from "../../components/recommendation/AnalysisLoading";

/**
 * 상품 평가를 기다리는 페이지. 상품 상세의 나와 맞는지 알아보기, 평가할 제품 고르기에서 온다.
 *
 * 이 페이지로 오는 요청은 모두 상품 평가라 서버가 시나리오를 알려 주기 전에도 평가 문구로 시작한다.
 * 신형식 job 은 상태 응답에 단계 목록(steps)이 와서 그대로 그리고, 예전 형식 job 은 단계 이름만 온다.
 */
export function RecommendationLoadingPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { jobId?: string; query?: string; productName?: string; productId?: string } | null };
  const jobId = state?.jobId;
  const [progress, setProgress] = useState<number | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [scenario, setScenario] = useState<string>("S1_EVALUATE");
  const [steps, setSteps] = useState<AnalysisStep[] | null>(null);
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
        // 같은 상태 API 다. 신형식 job 이면 scenario·steps 가 함께 온다.
        const response = await withDeadline(getQueryStatus(jobId!), Math.min(15_000, deadline - Date.now()));
        if (stopped) return;
        const data = validateAnalysisStatus(response.data);
        const raw = response.data;
        setNotice("");
        setProgress(data.progress);
        setStep(data.step);
        if (typeof raw?.scenario === "string" && raw.scenario) setScenario(raw.scenario);
        setSteps(Array.isArray(raw?.steps) ? raw.steps : null);
        if (data.status === "COMPLETED") { navigate("/recommendation/result", { state: { jobId }, replace: true }); return; }
        if (data.status === "FAILED" || data.status === "NEEDS_CLARIFICATION") {
          forgetAnalysisJob(jobId!);
          setEnded(true);
          if (data.status === "FAILED") setNotice("분석에 실패했어요. 이전 화면에서 다시 시도해주세요.");
          else { setStep("추가 정보가 필요해요"); setNotice("추가 질문 화면은 아직 연결되지 않았어요. 이전 화면에서 요청을 수정해주세요."); }
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

  return (
    <AppLayout>
      <section className="px-5 pb-8 pt-10">
        <PageHeader title={analysisCopy(scenario).header} onBack={() => navigate(-1)} />
        <div className="mt-5"><SearchField variant="outlined" value={state?.query ?? state?.productName ?? "맞춤 화장품 추천"} /></div>
        <AnalysisLoading
          scenario={scenario}
          steps={steps}
          step={step}
          progress={progress}
          paused={Boolean(notice) || !jobId}
        />
        {notice && <p role="status" className="mt-3 text-center text-caption text-gray-400">{notice}</p>}
        {notice && jobId && !ended && <button type="button" onClick={() => { setNotice(""); setPollAttempt(value => value + 1); }} className="mt-3 min-h-10 w-full text-caption font-semibold text-primary-600">분석 상태 다시 확인</button>}
        {notice && ended && <button type="button" onClick={() => navigate(-1)} className="mt-3 min-h-10 w-full text-caption font-semibold text-primary-600">이전 화면으로 돌아가기</button>}
        {!jobId && <p className="mt-3 text-center text-caption text-gray-300">요청 정보가 없어요. 이전 화면에서 다시 시작해주세요.</p>}
      </section>
    </AppLayout>
  );
}
