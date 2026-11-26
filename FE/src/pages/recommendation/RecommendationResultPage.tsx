import { useEffect, useState } from "react";
import { Shuffle, Sparkles, UsersRound } from "lucide-react";
import type { QueryResult } from "../../api/recommendationQueryApi";
import { EvaluationReport } from "../../components/search/EvaluationReport";
import { RelatedProductRow } from "../../components/search/RelatedProductRow";
import { useLocation, useNavigate } from "react-router-dom";
import {
  type RecommendationResultResponse,
  getRecommendationResult,
} from "../../api/recommendationApi";
import { PageHeader } from "../../components/common/PageHeader";
import { ProductThumbnail } from "../../components/common/ProductThumbnail";
import AppLayout from "../../layouts/AppLayout";

function fmt(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString("ko-KR") + "원";
}

/**
 * 세부 점수 항목. 상품 기준 추천은 항목마다 0~100 점을 주고, 항목별 가중치는 내려주지 않는다.
 * 그래서 몇 점 만점의 몇 점(28/30)이 아니라 항목 점수(0~100)를 그대로 보여준다.
 * 이름은 AI 의 점수 항목 이름(contracts/score.py SCORE_LABELS)과 맞춘다.
 */
const BREAKDOWN_ROWS = [
  { key: "personalization", label: "내 피부 적합" },
  { key: "reviewScore", label: "후기 일치" },
  { key: "budgetFit", label: "예산 적합" },
  { key: "priceValue", label: "가격 대비 가치" },
] as const;

function ScoreBreakdown({
  breakdown,
}: {
  breakdown: NonNullable<RecommendationResultResponse["mainRecommendations"][number]["breakdown"]>;
}) {
  const rows = BREAKDOWN_ROWS.filter((row) => breakdown[row.key] != null);
  if (rows.length === 0) return null;
  return (
    <section className="mt-4 rounded-xl border border-gray-200 bg-white p-4" aria-labelledby="score-breakdown-title">
      <h2 id="score-breakdown-title" className="text-body2 font-semibold text-gray-500">
        이 점수는 이렇게 나왔어요
      </h2>
      <ul className="mt-3 grid gap-3">
        {rows.map(({ key, label }) => {
          const score = Math.max(0, Math.min(100, Math.round(breakdown[key] ?? 0)));
          return (
            <li key={key}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-caption font-semibold text-gray-500">{label}</span>
                <span className="text-caption tabular-nums text-gray-400">
                  <span className="font-semibold text-primary-600">{score}</span> / 100
                </span>
              </div>
              <div
                className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-primary-50"
                role="meter"
                aria-label={label}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={score}
              >
                <div
                  className="h-full w-full origin-left rounded-full bg-primary-500"
                  style={{ transform: `scaleX(${score / 100})` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ProductImage({ url, alt }: { url: string | null; alt: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-xl bg-primary-50">
      {url ? (
        <img src={url} alt={alt} className="h-full w-full object-contain" />
      ) : (
        <ProductThumbnail className="h-full w-full bg-primary-50" shape={alt.includes("쿠션") ? "cushion" : "bottle"} />
      )}
    </div>
  );
}

export function RecommendationResultPage() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { jobId?: string } | null };
  const jobId = state?.jobId;
  const [result, setResult] = useState<RecommendationResultResponse | null>(null);
  // 신형식(상품 평가 S1_EVALUATE) 결과. 같은 결과 조회 API 가 job 종류에 따라 모양을 바꿔 준다.
  const [evaluation, setEvaluation] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    getRecommendationResult(jobId)
      .then((res) => {
        const data: unknown = res.data;
        if (data && typeof data === "object" && Array.isArray((data as QueryResult).items)) {
          setEvaluation(data as QueryResult);
        } else {
          setResult(res.data);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex h-screen flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto scrollbar-none">
        <section className="flex items-center justify-center">
          <div className="h-8 w-8 motion-safe:animate-spin rounded-full border-2 border-primary-200 border-t-primary-500" />
        </section>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (evaluation) {
    const item = evaluation.items[0];
    return (
      <AppLayout>
        <div className="flex h-screen flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto scrollbar-none">
            <section className="overflow-hidden px-6 pb-10 pt-10">
              <PageHeader title="추천 결과 보고서" onBack={() => navigate(-1)} />
              {evaluation.appliedPreference?.text && (
                <p className="mt-4 text-[11px] leading-5 text-gray-400">{evaluation.appliedPreference.text}</p>
              )}
              {item ? (
                <EvaluationReport item={item} onOpen={() => navigate(`/product/${item.productId}`)} />
              ) : (
                <p className="mt-10 text-center text-body2 text-gray-400">평가 결과를 만들지 못했어요</p>
              )}
              <RelatedProductRow
                icon={UsersRound}
                title="나와 비슷한 사람들이 쓰는 제품"
                description="피부 타입과 고민이 비슷한 분들이 만족한 제품이에요"
                products={(evaluation.similarUserProducts ?? []).map((p) => ({
                  productId: p.productId, name: p.name, brand: p.brand, price: p.price,
                }))}
                onOpen={(p) => navigate(`/product/${p.productId}`)}
              />
              <RelatedProductRow
                icon={Shuffle}
                title="비슷한 대체 제품"
                description="성분과 특징이 비슷한 다른 선택지예요"
                products={(evaluation.alternatives ?? []).map((p) => ({
                  productId: p.productId, name: p.name, brand: p.brand, price: p.price,
                  tag: p.similarity != null ? `유사도 ${Math.round(p.similarity * 100)}%` : null,
                }))}
                onOpen={(p) => navigate(`/product/${p.productId}`)}
              />
            </section>
          </div>
        </div>
      </AppLayout>
    );
  }

  const main = result?.mainRecommendations?.[0];
  // 위의 매칭 점수는 점수가 가장 높은 추천 상품의 총점이다. 그 상품의 세부 점수로 풀어 보여준다.
  const scored = (result?.mainRecommendations ?? []).reduce<typeof main>(
    (best, item) => ((item.totalScore ?? -1) > (best?.totalScore ?? -1) ? item : best),
    undefined,
  );
  const openProduct = (id: string) => navigate(`/product/${id}`);

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
      <section className="overflow-hidden px-6 pb-6 pt-10">
        <PageHeader title="추천 결과 보고서" onBack={() => navigate(-1)} />

        {/* 매칭 점수 카드 */}
        <section className="relative mt-5 overflow-hidden rounded-2xl bg-gray-500 p-7 text-white">
          <div>
            <p className="text-body2 text-primary-300">AI 매칭 완료</p>
            <p className="mt-1 text-[42px] font-bold leading-none">
              {result?.matchScore ?? "—"}
              {result?.matchScore != null && <span className="text-body1"> 점</span>}
            </p>
            <p className="mt-3 text-body2 text-primary-300">
              {result?.matchLabel ?? "인생템 확률 매칭"}
            </p>
          </div>
          <span className="absolute right-12 top-5 h-[92px] w-[92px] rounded-full bg-gray-400" />
          <span className="absolute right-7 top-16 h-[66px] w-[66px] rounded-full bg-primary-700" />
          <Sparkles aria-hidden="true" className="absolute right-[74px] top-[74px] h-7 w-7 text-white" />
        </section>

        {/* 세부 점수 */}
        {scored?.breakdown && <ScoreBreakdown breakdown={scored.breakdown} />}

        {/* AI 추천 이유 */}
        {result?.aiReason && (
          <section className="mt-4 rounded-xl border border-primary-100 bg-primary-50 p-4">
            <h2 className="text-body2 font-semibold text-primary-600">AI가 분석한 추천 이유</h2>
            <p className="mt-2 text-caption leading-6 text-gray-500">{result.aiReason}</p>
          </section>
        )}

        {/* 메인 추천 */}
        {main && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">추천 상품</h2>
            <button type="button" onClick={() => openProduct(main.id)} className="mt-3 flex w-full items-center gap-4 rounded-xl border border-primary-300 bg-white p-4 text-left">
              <div className="h-[70px] w-[70px] shrink-0">
                <ProductImage url={main.imageUrl} alt={main.name} />
              </div>
              <div className="flex-1">
                <p className="text-caption text-gray-300">{main.brand}</p>
                <p className="text-body2 text-gray-500">{main.name}</p>
                <p className="mt-1 text-body1 text-primary-500">{fmt(main.price)}</p>
              </div>
              {main.totalScore != null && (
                <div className="text-right">
                  <p className="text-h3 text-primary-500">{main.totalScore}점</p>
                  <p className="text-caption text-gray-300">매칭</p>
                </div>
              )}
            </button>
          </section>
        )}

        {/* 나와 비슷한 사람들 */}
        {result?.similarUserProducts && result.similarUserProducts.length > 0 && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">나와 비슷한 사람들은?</h2>
            <p className="text-caption text-gray-300">비슷한 피부 타입의 실제 만족 제품</p>
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
              {result.similarUserProducts.map((p) => (
                <button type="button"
                  className="min-w-[154px] cursor-pointer rounded-2xl border border-gray-200 bg-white p-3 text-center"
                  key={p.id}
                  onClick={() => openProduct(p.id)}
                >
                  <div className="h-[94px] overflow-hidden rounded-lg">
                    <ProductImage url={p.imageUrl} alt={p.name} />
                  </div>
                  <p className="mt-3 truncate text-body2 text-gray-500">{p.name}</p>
                  <p className="truncate text-caption text-gray-300">{p.brand}</p>
                  {p.satisfactionPercent != null && (
                    <p className="mt-1 text-caption text-primary-500">
                      만족도 {p.satisfactionPercent}%
                    </p>
                  )}
                  <p className="mt-1 text-caption text-gray-400">{fmt(p.price)}</p>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* 대체 상품 */}
        {result?.alternativeProducts && result.alternativeProducts.length > 0 && (
          <section className="mt-4">
            <h2 className="text-body1 text-gray-500">유사한 대체 상품</h2>
            <div className="mt-3 grid gap-3">
              {result.alternativeProducts.map((p) => (
                <button type="button"
                  className="flex cursor-pointer items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 text-left"
                  key={p.id}
                  onClick={() => openProduct(p.id)}
                >
                  <div className="h-[60px] w-[60px] shrink-0">
                    <ProductImage url={p.imageUrl} alt={p.name} />
                  </div>
                  <div className="flex-1">
                    <p className="text-body2 text-gray-500">{p.name}</p>
                    <p className="text-caption text-primary-500">
                      <span className="flex gap-2">
                        {p.ingredientSimilarity != null && <span>성분 유사도 {p.ingredientSimilarity}%</span>}
                        <span>{p.brand}</span>
                      </span>
                    </p>
                    <p className="mt-1 text-body1 text-gray-500">{fmt(p.price)}</p>
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}


        <button
          className="mt-4 h-14 w-full rounded-xl bg-primary-600 text-body1 font-semibold text-white"
          onClick={() => navigate("/home")}
          type="button"
        >
          홈으로 돌아가기
        </button>
      </section>
        </div>
      </div>
    </AppLayout>
  );
}
