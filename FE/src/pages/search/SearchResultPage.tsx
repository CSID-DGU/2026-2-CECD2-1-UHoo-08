import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  aiSearch,
  recordProductView,
  type AiSearchProduct,
} from "../../api/productApi";
import {
  getRecommendationResult,
  getRecommendationStatus,
  type RecommendationResultResponse,
} from "../../api/recommendationApi";
import { BottomNav } from "../../components/common/BottomNav";
import { PageHeader } from "../../components/common/PageHeader";
import { ChevronRight, History, Plus } from "lucide-react";
import { addWishlist, deleteWishlist, getWishlists } from "../../api/wishlistApi";
import { SearchProductCard } from "../../components/search/SearchProductCard";
import { SearchField } from "../../components/common/SearchField";
import { RecommendationRefinementSheet } from "../../components/recommendation/RecommendationRefinementSheet";
import {
  RefinementHistorySheet,
  type SearchHistoryEntry,
} from "../../components/recommendation/RefinementHistorySheet";
import { SearchEntry } from "../../components/search/SearchEntry";
import { SearchAnalysisLoading } from "../../components/search/SearchAnalysisLoading";
import { saveLastSearch } from "../../lib/localHistory";
import {
  AnalysisEndedError,
  beginSearchAnalysis,
  forgetAnalysisJob,
  validateAnalysisStatus,
  withDeadline,
} from "../../lib/searchAnalysis";
import {
  deleteSearchView,
  readSearchView,
  searchViewKey,
  writeSearchView,
} from "../../lib/searchViewStorage";
import AppLayout from "../../layouts/AppLayout";

const CATEGORY_LABEL: Record<string, string> = {
  base: "베이스 메이크업",
  sun: "선케어",
  lip: "립 메이크업",
  skincare: "스킨케어",
};
const RESULT_BASES = [
  { id: "self", label: "내 피부 기준" },
  { id: "popular", label: "전체 인기" },
  { id: "other", label: "다른 사람" },
] as const;
type ResultBasis = (typeof RESULT_BASES)[number]["id"];
interface SearchSnapshot extends SearchHistoryEntry {
  query: string;
  baseQuery: string;
  category: string;
  analysis: RecommendationResultResponse | null;
  analysisNotice: string;
  jobId: string | null;
}

interface SavedSearchView {
  snapshot: SearchSnapshot;
  history: SearchSnapshot[];
  historyIndex: number;
  scrollTop: number;
  basis?: ResultBasis;
}
// Each browser-history entry owns its result; a new search entry starts fresh.
// Session storage also preserves results across a reload in the detail page.
const searchViews = new Map<string, SavedSearchView>();

export function SearchResultPage() {
  const location = useLocation();
  return <SearchResultContent key={location.key} />;
}

function SearchResultContent() {
  const navigate = useNavigate();
  const { state, key } = useLocation() as {
    state: { query?: string; entryScenario?: string } | null;
    key: string;
  };
  const cacheKey = searchViewKey(key);
  const [saved] = useState(() => {
    const view =
      searchViews.get(cacheKey) ?? readSearchView<SavedSearchView>(cacheKey);
    if (
      !view ||
      !Array.isArray(view.history) ||
      !view.snapshot ||
      !Array.isArray(view.snapshot.products) ||
      !view.history[view.historyIndex]
    )
      return undefined;
    return view;
  });
  const scrollContainer = useRef<HTMLDivElement>(null);
  const initialQuery = state?.query ?? "";
  const [baseQuery, setBaseQuery] = useState(
    saved?.snapshot.baseQuery ?? initialQuery,
  );
  const [submittedQuery, setSubmittedQuery] = useState(
    saved?.snapshot.query ?? initialQuery,
  );
  const [conditions, setConditions] = useState<string[]>(
    saved?.snapshot.conditions ?? [],
  );
  const [products, setProducts] = useState<AiSearchProduct[]>(
    saved?.snapshot.products ?? [],
  );
  const [category, setCategory] = useState(saved?.snapshot.category ?? "");
  const [basis, setBasis] = useState<ResultBasis>(saved?.basis ?? "self");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState<RecommendationResultResponse | null>(
    saved?.snapshot.analysis ?? null,
  );
  const [analysisNotice, setAnalysisNotice] = useState(
    saved?.snapshot.analysisNotice ?? "",
  );
  const [analysisJobId, setAnalysisJobId] = useState<string | null>(
    saved?.snapshot.jobId ?? null,
  );
  const [analysisStep, setAnalysisStep] = useState("");
  const [analysisProgress, setAnalysisProgress] = useState<number | null>(null);
  const [sheet, setSheet] = useState<"add" | "edit" | "history" | null>(null);
  const [history, setHistory] = useState<SearchSnapshot[]>(
    saved?.history ?? [],
  );
  const [historyIndex, setHistoryIndex] = useState(saved?.historyIndex ?? -1);
  const historyIndexRef = useRef(saved?.historyIndex ?? -1);
  const searchVersion = useRef(0);
  const previousResult =
    historyIndex > 0 ? history[historyIndex - 1] : undefined;
  const previousRanks = new Map(
    previousResult?.products.map((product, index) => [
      product.productId,
      index,
    ]),
  );
  const newProductCount = previousResult
    ? products.filter((product) => !previousRanks.has(product.productId)).length
    : 0;
  const [wishlistIds, setWishlistIds] = useState<Record<string, string> | null>(null);
  const wishlistRequest = useRef<Promise<Record<string, string>> | null>(null);
  function loadWishlistIds() {
    if (!wishlistRequest.current) {
      wishlistRequest.current = getWishlists().then(({ data }) => {
        if (!Array.isArray(data?.wishlists)) throw new Error("INVALID_WISHLIST_RESPONSE");
        return Object.fromEntries(data.wishlists.map(item => [item.product.id, item.wishlistId]));
      }).catch(error => { wishlistRequest.current = null; throw error; });
    }
    return wishlistRequest.current;
  }
  useEffect(() => {
    let active = true;
    loadWishlistIds().then(ids => { if (active) setWishlistIds(ids); }).catch(() => {});
    return () => { active = false; };
  }, []);
  async function toggleWishlist(productId: string) {
    const ids = wishlistIds ?? await loadWishlistIds();
    const wishlistId = ids[productId];
    if (wishlistId) {
      await deleteWishlist(wishlistId);
      setWishlistIds(previous => { const next = { ...(previous ?? ids) }; delete next[productId]; return next; });
    } else {
      const { data } = await addWishlist(productId);
      if (!data?.wishlistId) throw new Error("INVALID_WISHLIST_RESPONSE");
      setWishlistIds(previous => ({ ...(previous ?? ids), [productId]: data.wishlistId }));
    }
  }

  useEffect(() => {
    if (!saved && initialQuery)
      void runSearch(initialQuery, [], "처음 검색", true);
    return () => {
      searchVersion.current += 1;
    };
  }, [initialQuery]);

  useLayoutEffect(() => {
    if (saved && scrollContainer.current)
      scrollContainer.current.scrollTop = saved.scrollTop;
  }, [saved]);

  useLayoutEffect(() => {
    if (loading || error || historyIndex < 0) return;
    const snapshot = {
      ...history[historyIndex],
      analysis,
      analysisNotice,
      jobId: analysisJobId,
    };
    searchViews.set(cacheKey, {
      snapshot,
      history,
      historyIndex,
      basis,
      scrollTop: scrollContainer.current?.scrollTop ?? 0,
    });
    writeSearchView(cacheKey, searchViews.get(cacheKey));
    if (searchViews.size > 20)
      searchViews.delete(searchViews.keys().next().value!);
  }, [
    cacheKey,
    history,
    historyIndex,
    basis,
    loading,
    error,
    analysis,
    analysisNotice,
    analysisJobId,
  ]);

  useLayoutEffect(() => {
    const container = scrollContainer.current;
    const persist = () => {
      const view = searchViews.get(cacheKey);
      if (!view) return;
      view.scrollTop = container?.scrollTop ?? view.scrollTop;
      writeSearchView(cacheKey, view);
    };
    window.addEventListener("pagehide", persist);
    return () => {
      persist();
      window.removeEventListener("pagehide", persist);
    };
  }, [cacheKey]);

  async function collectAnalysis(jobId: string, version: number) {
    const deadline = Date.now() + 180_000;
    while (version === searchVersion.current) {
      if (Date.now() >= deadline) throw new Error("TIMEOUT");
      const statusResponse = await withDeadline(
        getRecommendationStatus(jobId),
        Math.min(15_000, deadline - Date.now()),
      );
      if (version !== searchVersion.current) return null;
      const data = validateAnalysisStatus(statusResponse.data);
      setAnalysisStep(
        data.step ||
          (data.status === "PENDING"
            ? "분석 시작을 기다리고 있어요"
            : "등록한 피부 정보로 후보를 분석하고 있어요"),
      );
      setAnalysisProgress(
        data.progress == null
          ? null
          : Math.min(100, Math.max(0, data.progress)),
      );
      if (data.status === "COMPLETED") {
        const response = await withDeadline(
          getRecommendationResult(jobId),
          15_000,
        );
        if (version !== searchVersion.current) return null;
        setAnalysis(response.data);
        setAnalysisNotice("");
        return response.data;
      }
      if (data.status === "FAILED" || data.status === "NEEDS_CLARIFICATION") {
        forgetAnalysisJob(jobId);
        setAnalysisJobId(null);
        setHistory((previous) =>
          previous.map((entry) =>
            entry.jobId === jobId ? { ...entry, jobId: null } : entry,
          ),
        );
        throw new AnalysisEndedError(data.status);
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    return null;
  }

  async function runSearch(
    base: string,
    nextConditions: string[],
    title: string,
    fresh = false,
  ) {
    if (!base.trim()) return;
    const normalized = [
      ...new Set(nextConditions.map((item) => item.trim()).filter(Boolean)),
    ];
    const requestQuery = normalized.length
      ? `${base.trim()}\n추가 조건: ${normalized.join(", ")}`
      : base.trim();
    const version = ++searchVersion.current;
    searchViews.delete(cacheKey);
    deleteSearchView(cacheKey);
    setBaseQuery(base.trim());
    setSubmittedQuery(requestQuery);
    setConditions(normalized);
    setProducts([]);
    setAnalysis(null);
    setAnalysisNotice("");
    setAnalysisJobId(null);
    setAnalysisProgress(null);
    setError("");
    setSheet(null);
    setBasis("self");
    setLoading(true);
    setSearching(true);
    setAnalysisStep("입력하신 요청에 맞는 후보를 찾고 있어요");
    if (fresh) {
      setHistory([]);
      setHistoryIndex(-1);
      historyIndexRef.current = -1;
    }
    try {
      const response = await withDeadline(aiSearch(requestQuery), 60_000);
      if (version !== searchVersion.current) return;
      setProducts(response.products);
      setCategory(response.category);
      setSearching(false);
      saveLastSearch({
        query: requestQuery,
        category: response.category,
        intent: response.intent,
        products: response.products,
      });
      let result: RecommendationResultResponse | null = null;
      let notice = "";
      let jobId: string | null = null;
      if (response.products[0] && response.intent !== "PRODUCT_NAME") {
        setAnalysisStep("검색 첫 번째 제품을 기준으로 분석을 시작하고 있어요");
        try {
          const { data } = await withDeadline(
            beginSearchAnalysis(requestQuery, response.products[0].productId),
            30_000,
          );
          if (version !== searchVersion.current) return;
          jobId = data.jobId;
          setAnalysisJobId(jobId);
          result = await collectAnalysis(jobId, version);
        } catch (error) {
          if (error instanceof AnalysisEndedError) jobId = null;
          notice =
            error instanceof AnalysisEndedError &&
            error.status === "NEEDS_CLARIFICATION"
              ? "추가 정보가 필요해요. 추가 질문 화면은 아직 연결되지 않았어요. 검색 조건을 더 구체적으로 수정해주세요."
              : "피부 분석을 완료하지 못했어요. 검색한 제품은 먼저 보여드릴게요. 피부 프로필과 연결 상태를 확인해주세요.";
          if (version === searchVersion.current) setAnalysisNotice(notice);
        }
      }
      if (version !== searchVersion.current) return;
      const snapshot: SearchSnapshot = {
        title,
        query: requestQuery,
        baseQuery: base.trim(),
        conditions: normalized,
        products: response.products,
        category: response.category,
        analysis: result,
        analysisNotice: notice,
        jobId,
      };
      const nextIndex = historyIndexRef.current + 1;
      setHistory((previous) => [...previous.slice(0, nextIndex), snapshot]);
      historyIndexRef.current = nextIndex;
      setHistoryIndex(nextIndex);
    } catch {
      if (version === searchVersion.current)
        setError("검색 중 오류가 발생했어요. 다시 시도해주세요.");
    } finally {
      if (version === searchVersion.current) setLoading(false);
    }
  }

  function restoreHistory(index: number) {
    const snapshot = history[index];
    if (!snapshot) return;
    searchVersion.current += 1;
    setSubmittedQuery(snapshot.query);
    setBaseQuery(snapshot.baseQuery);
    setConditions(snapshot.conditions);
    setProducts(snapshot.products);
    setCategory(snapshot.category);
    setAnalysis(snapshot.analysis);
    setAnalysisNotice(snapshot.analysisNotice);
    setAnalysisJobId(snapshot.jobId);
    setHistoryIndex(index);
    historyIndexRef.current = index;
    setLoading(false);
    setError("");
    setSheet(null);
  }

  async function resumeAnalysis() {
    if (!analysisJobId || loading) return;
    const version = searchVersion.current;
    setLoading(true);
    setSearching(false);
    setAnalysisNotice("");
    try {
      const result = await collectAnalysis(analysisJobId, version);
      if (result && version === searchVersion.current)
        setHistory((previous) =>
          previous.map((entry, index) =>
            index === historyIndexRef.current
              ? { ...entry, analysis: result, analysisNotice: "" }
              : entry,
          ),
        );
    } catch (error) {
      if (version === searchVersion.current) {
        const notice =
          error instanceof AnalysisEndedError
            ? error.status === "NEEDS_CLARIFICATION"
              ? "추가 정보가 필요해요. 추가 질문 화면은 아직 연결되지 않았어요. 검색 조건을 더 구체적으로 수정해주세요."
              : "추천 분석에 실패했어요. 피부 프로필과 연결 상태를 확인한 뒤 다시 시도해주세요."
            : "아직 분석 결과를 확인하지 못했어요. 잠시 후 진행 상태를 다시 확인해주세요.";
        setAnalysisNotice(notice);
        setHistory((previous) =>
          previous.map((entry, index) =>
            index === historyIndexRef.current
              ? {
                  ...entry,
                  analysisNotice: notice,
                  jobId:
                    error instanceof AnalysisEndedError ? null : entry.jobId,
                }
              : entry,
          ),
        );
      }
    } finally {
      if (version === searchVersion.current) setLoading(false);
    }
  }

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div
          ref={scrollContainer}
          onScroll={(event) => {
            const view = searchViews.get(cacheKey);
            if (view) view.scrollTop = event.currentTarget.scrollTop;
          }}
          className="flex-1 overflow-y-auto scrollbar-none"
        >
          <section className="search-results-screen flex flex-col px-[18px] pb-44 pt-7 text-slate-800">
            <PageHeader
              title={
                loading
                  ? searching
                    ? "검색 중"
                    : "검색 · 피부 분석 중"
                  : submittedQuery
                    ? "검색 결과"
                    : "검색"
              }
              onBack={() => navigate(-1)}
            />
            <div className="mt-5">
              <SearchField
                className="search-results-field"
                key={baseQuery}
                editable
                variant="outlined"
                placeholder="제품명이나 궁금한 점을 입력하세요"
                value={baseQuery}
                onSubmit={(value) =>
                  void runSearch(value, [], "처음 검색", true)
                }
              />
            </div>
            {submittedQuery && !loading && !error && (
              <>
                <div
                  role="tablist"
                  aria-label="검색 결과 기준"
                  className="mt-4 grid grid-cols-3 gap-1 rounded-xl bg-[#F2F6FC] p-1"
                >
                  {RESULT_BASES.map((item, index) => (
                    <button
                      key={item.id}
                      id={`basis-tab-${item.id}`}
                      type="button"
                      role="tab"
                      aria-selected={basis === item.id}
                      aria-controls="basis-results"
                      tabIndex={basis === item.id ? 0 : -1}
                      onClick={() => setBasis(item.id)}
                      onKeyDown={(event) => {
                        const next =
                          event.key === "ArrowRight"
                            ? (index + 1) % RESULT_BASES.length
                            : event.key === "ArrowLeft"
                              ? (index + RESULT_BASES.length - 1) %
                                RESULT_BASES.length
                              : event.key === "Home"
                                ? 0
                                : event.key === "End"
                                  ? RESULT_BASES.length - 1
                                  : null;
                        if (next != null) {
                          event.preventDefault();
                          setBasis(RESULT_BASES[next].id);
                          document
                            .getElementById(
                              `basis-tab-${RESULT_BASES[next].id}`,
                            )
                            ?.focus();
                        }
                      }}
                      className={`min-h-10 rounded-lg px-1 text-xs font-semibold transition-colors ${basis === item.id ? "bg-[#9DBDE9] text-[#203D66]" : "text-slate-500 hover:bg-white/60"}`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </>
            )}
            {!submittedQuery && state?.entryScenario === "refine" && (
              <p className="mt-4 rounded-xl bg-primary-50 p-3 text-xs leading-5 text-primary-600">
                먼저 원하는 제품을 검색해주세요. 결과 화면의 ‘조건 추가’와 ‘조건
                수정’으로 후보를 좁히고, 수정 이력에서 이전 결과도 확인할 수
                있어요.
              </p>
            )}
            {!submittedQuery && (
              <SearchEntry
                onSearch={(value) =>
                  void runSearch(value, [], "처음 검색", true)
                }
              />
            )}

            {submittedQuery && !loading && !error && (
              <section aria-label="검색 조건" className="mt-2 border-b border-slate-100 pb-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">현재 조건</p>
                  <div className="flex items-center gap-3">
                    {previousResult && <button type="button" onClick={() => restoreHistory(historyIndex - 1)} className="min-h-10 text-xs text-slate-500">되돌리기</button>}
                    <button type="button" onClick={() => setSheet("edit")} className="flex min-h-10 items-center text-xs text-primary-600">조건 수정 <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {[baseQuery, ...conditions].map((condition, index) => <span key={`${index}-${condition}`} className="max-w-full break-words rounded-md bg-[#F2F6FC] px-2.5 py-1.5 text-[11px] leading-4 text-slate-600">{condition}</span>)}
                </div>
              </section>
            )}
            {loading && (
              <SearchAnalysisLoading
                searching={searching}
                step={
                  searching
                    ? "입력한 요청에 맞는 제품을 찾고 있어요"
                    : analysisStep
                }
                progress={searching ? null : analysisProgress}
              />
            )}
            {!loading && error && (
              <div role="alert" className="mt-8 text-center">
                <p className="text-body2 text-gray-300">{error}</p>
                <button
                  type="button"
                  onClick={() =>
                    void runSearch(baseQuery, conditions, "다시 검색")
                  }
                  className="mt-3 min-h-10 text-caption font-semibold text-primary-600"
                >
                  다시 검색
                </button>
              </div>
            )}
            {!loading && analysisNotice && (
              <div role="status" className="mt-5 rounded-xl bg-primary-50 p-4">
                <p className="text-caption leading-5 text-gray-400">
                  {analysisNotice}
                </p>
                <button
                  type="button"
                  onClick={() =>
                    analysisNotice.startsWith("추가 정보가 필요해요.")
                      ? setSheet("edit")
                      : analysisJobId
                        ? void resumeAnalysis()
                        : void runSearch(
                            baseQuery,
                            conditions,
                            "분석 다시 시도",
                          )
                  }
                  className="mt-2 min-h-10 text-caption font-semibold text-primary-600"
                >
                  {analysisNotice.startsWith("추가 정보가 필요해요.")
                    ? "조건 수정"
                    : analysisJobId
                      ? "분석 상태 다시 확인"
                      : "다시 시도"}
                </button>
              </div>
            )}
            {submittedQuery && !loading && !error && (
              <div
                id="basis-results"
                role="tabpanel"
                aria-labelledby={`basis-tab-${basis}`}
              >
                {!loading &&
                  !error &&
                  basis === "self" &&
                  products.length > 0 && (
                    <>
                      <div className="mt-5 flex items-center justify-between gap-2">
                        <div>
                        <h2 className="mb-1 text-base font-semibold text-slate-800">요청에 맞는 제품</h2>
                        <p className="text-xs leading-5 text-slate-500">
                          {category
                            ? `${CATEGORY_LABEL[category] ?? category} · `
                            : ""}
                          {products.length}개 결과
                        </p>
                        </div>
                        <span className="text-xs text-slate-500">검색 결과 순</span>
                      </div>
                      {previousResult && (
                        <p className="text-[11px] text-primary-500">
                          새로 찾은 후보 {newProductCount}개
                        </p>
                      )}
                      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-5">
                        {products.map((product, index) => {
                          const oldRank = previousRanks.get(product.productId);
                          const rankLabel = !previousResult
                            ? null
                            : oldRank === undefined
                              ? "새로 찾음"
                              : oldRank === index
                                ? "순위 유지"
                                : oldRank > index
                                  ? `${oldRank - index}계단 ↑`
                                  : null;
                          const personalization =
                            analysis?.mainRecommendations.find(
                              (item) => item.id === product.productId,
                            )?.breakdown?.personalization;
                          const hasReport =
                            analysis &&
                            (analysis.baseProduct?.id === product.productId ||
                              analysis.mainRecommendations.some(
                                (item) => item.id === product.productId,
                              ));
                          return (
                            <SearchProductCard
                              key={product.productId}
                              product={product}
                              rank={index + 1}
                              rankLabel={rankLabel}
                              personalization={personalization}
                              saved={Boolean(wishlistIds?.[product.productId])}
                              onToggleSaved={() => toggleWishlist(product.productId)}
                              onOpen={() => {
                                recordProductView(product.productId).catch(() => {});
                                navigate(`/product/${product.productId}`, { state: hasReport ? { jobId: analysis.jobId } : null });
                              }}
                            />
                          );
                        })}
                      </div>
                    </>
                  )}
                {!loading &&
                  !error &&
                  basis === "self" &&
                  !products.length &&
                  submittedQuery && (
                    <div className="mt-12 text-center">
                      <p className="text-body2 text-gray-400">
                        검색 결과가 없어요
                      </p>
                      <p className="mt-2 text-caption text-gray-300">
                        조건을 수정하거나 다른 표현으로 다시 검색해 보세요
                      </p>
                    </div>
                  )}
                {submittedQuery && !loading && !error && basis !== "self" && (
                  <div className="px-4 py-14 text-center">
                    <p className="text-sm font-semibold text-gray-500">
                      {basis === "popular"
                        ? "전체 인기 결과를 준비하고 있어요"
                        : "다른 사람 기준 검색을 준비하고 있어요"}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-gray-300">
                      {basis === "popular"
                        ? "검색 조건에 맞는 인기 순위는 아직 제공되지 않아요."
                        : "다른 사람의 피부 정보를 적용한 검색은 아직 제공되지 않아요."}
                    </p>
                    <button
                      type="button"
                      onClick={() => setBasis("self")}
                      className="mt-4 min-h-10 rounded-lg bg-primary-50 px-4 text-xs font-semibold text-primary-600"
                    >
                      현재 검색 결과 보기
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
      {submittedQuery && !loading && !error && (
        <div
          className="pointer-events-none fixed bottom-[88px] left-1/2 z-30 flex w-full max-w-[430px] -translate-x-1/2 items-center gap-3 px-[18px]"
          style={{ marginBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          {history.length > 1 && (
            <button
              type="button"
              onClick={() => setSheet("history")}
              className="pointer-events-auto flex min-h-11 items-center gap-1.5 rounded-[14px] border border-slate-200 bg-white px-3 text-xs text-slate-600 shadow-[0_4px_16px_rgba(32,61,102,0.12)]"
            >
              <History aria-hidden="true" className="h-4 w-4" /> 수정 이력 {history.length - 1}단계
            </button>
          )}
          <button
            type="button"
            onClick={() => setSheet("add")}
            className="pointer-events-auto ml-auto flex min-h-12 items-center gap-1.5 rounded-[14px] bg-[#9DBDE9] px-4 text-[13px] font-semibold text-[#203D66] shadow-[0_5px_18px_rgba(32,61,102,0.16)]"
          >
            <Plus aria-hidden="true" className="h-[18px] w-[18px]" /> 조건 추가
          </button>
        </div>
      )}
      <BottomNav compactSearch />
      {(sheet === "add" || sheet === "edit") && (
        <RecommendationRefinementSheet
          key={sheet}
          mode={sheet}
          baseQuery={baseQuery}
          conditions={conditions}
          onClose={() => setSheet(null)}
          onApply={(items, editedBase) => {
            const next = sheet === "add" ? [...conditions, ...items] : items;
            void runSearch(
              editedBase ?? baseQuery,
              next,
              sheet === "add" ? `조건 추가: ${items.join(" · ")}` : "조건 수정",
            );
          }}
        />
      )}
      {sheet === "history" && (
        <RefinementHistorySheet
          entries={history}
          activeIndex={historyIndex}
          onClose={() => setSheet(null)}
          onSelect={restoreHistory}
        />
      )}
    </AppLayout>
  );
}
