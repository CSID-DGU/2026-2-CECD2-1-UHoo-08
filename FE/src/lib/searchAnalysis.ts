import { requestRecommendation } from "../api/recommendationApi";
import { getAccessToken } from "./auth";

// Share job creation across repeated submissions and React effect replays.
// Retain the job ID so retrying status never creates another AI job.
const jobs = new Map<string, { createdAt: number; request: ReturnType<typeof requestRecommendation> }>();

export function beginSearchAnalysis(query: string, productId: string) {
  const key = JSON.stringify([getAccessToken(), query.trim(), productId]);
  const existing = jobs.get(key);
  if (existing && Date.now() - existing.createdAt < 600_000) return existing.request;
  for (const [id, job] of jobs) {
    if (Date.now() - job.createdAt >= 600_000) jobs.delete(id);
  }
  const request = requestRecommendation(productId, "", "any").catch(error => {
    jobs.delete(key);
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
