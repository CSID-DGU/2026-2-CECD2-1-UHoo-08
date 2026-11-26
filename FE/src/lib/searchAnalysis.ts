import { type RecommendationStatusResponse } from "../api/recommendationApi";
import { requestQuery } from "../api/recommendationQueryApi";
import { getAccessToken } from "./auth";

// Share job creation across repeated submissions and React effect replays.
// Retain the job ID so retrying status never creates another AI job.
const jobs = new Map<string, { createdAt: number; request: ReturnType<typeof requestQuery>; jobId?: string }>();

export function forgetAnalysisJob(jobId: string) {
  for (const [key, job] of jobs) {
    if (job.jobId === jobId) jobs.delete(key);
  }
}

export class AnalysisEndedError extends Error {
  readonly status: "FAILED" | "NEEDS_CLARIFICATION";
  constructor(status: "FAILED" | "NEEDS_CLARIFICATION") {
    super(status);
    this.status = status;
  }
}

export function validateAnalysisStatus(data: RecommendationStatusResponse | null | undefined) {
  if (!data || typeof data.status !== "string") throw new Error("INVALID_STATUS_RESPONSE");
  return {
    ...data,
    step: typeof data.step === "string" ? data.step : null,
    progress: typeof data.progress === "number" && Number.isFinite(data.progress)
      ? Math.min(100, Math.max(0, data.progress)) : null,
  };
}

export function beginSearchAnalysis(query: string, productId: string) {
  const key = JSON.stringify([getAccessToken(), query.trim(), productId]);
  const existing = jobs.get(key);
  if (existing && Date.now() - existing.createdAt < 600_000) return existing.request;
  for (const [id, job] of jobs) {
    if (Date.now() - job.createdAt >= 600_000) jobs.delete(id);
  }
  // 상품 기준 평가는 신형식(baseProductId)으로 요청한다. 결과에 점수 분해(score·weight)와
  // 비슷한 사람들·대체 제품이 함께 와서 보고서에 세부 점수를 그릴 수 있다.
  const request = requestQuery({ baseProductId: productId, basis: "SELF" }).then(response => {
    if (!response.data?.jobId) throw new Error("INVALID_JOB_RESPONSE");
    const job = jobs.get(key);
    if (job?.request === request) job.jobId = response.data.jobId;
    return response;
  }).catch(error => {
    if (jobs.get(key)?.request === request) jobs.delete(key);
    throw error;
  });
  jobs.set(key, { createdAt: Date.now(), request });
  return request;
}

export async function withDeadline<T>(request: Promise<T>, milliseconds: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      request,
      new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error("TIMEOUT")), milliseconds); }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}
