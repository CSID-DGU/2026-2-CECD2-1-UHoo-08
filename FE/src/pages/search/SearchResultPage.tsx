import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ChevronRight,
  History,
  Plus,
  Shuffle,
  Sparkles,
  Undo2,
  UsersRound,
} from "lucide-react";
import {
  recordProductView,
  searchProducts,
  type AiSearchProduct,
  type ProductSearchItem,
} from "../../api/productApi";
import {
  answerClarification,
  apiErrorCode,
  getQueryResult,
  getQueryStatus,
  getRefinementHistory,
  getRefinementOptions,
  requestQuery,
  requestRefinement,
  revertPreferenceChange,
  submitFeedback,
  type ClarifyField,
  type QueryResult,
  type RecommendationBasis,
  type RefinePresetKey,
  type RefinementOptions,
  type ResultItem,
} from "../../api/recommendationQueryApi";
import {
  addWishlist,
  deleteWishlist,
  getWishlists,
} from "../../api/wishlistApi";
import { BottomNav } from "../../components/common/BottomNav";
import { ClarifyForm } from "../../components/recommendation/ClarifyForm";
import {
  RecommendationFeedbackSheet,
  type FeedbackValue,
} from "../../components/recommendation/RecommendationFeedbackSheet";
import { RecommendationRefinementSheet } from "../../components/recommendation/RecommendationRefinementSheet";
import {
  RefinementHistorySheet,
  type RefinementHistoryEntry,
} from "../../components/recommendation/RefinementHistorySheet";
import { SearchAnalysisLoading } from "../../components/search/SearchAnalysisLoading";
import { SearchEntry } from "../../components/search/SearchEntry";
import { SearchProductCard } from "../../components/search/SearchProductCard";
import { SearchTopBar } from "../../components/search/SearchTopBar";
import { RelatedProductRow } from "../../components/search/RelatedProductRow";
import { BundleResult } from "../../components/search/BundleResult";
import { MOCK_UNREADY, isMockJob, mockBundleResult } from "../../mocks/unready";
import { EvaluationReport } from "../../components/search/EvaluationReport";
import { ProductLensSheet } from "../../components/search/ProductLensSheet";
import { useProductLens } from "../../components/search/useProductLens";
import { addRecentSearch, saveLastSearch } from "../../lib/localHistory";
import { withDeadline } from "../../lib/searchAnalysis";
import {
  deleteSearchView,
  readSearchView,
  searchViewKey,
  writeSearchView,
} from "../../lib/searchViewStorage";
import AppLayout from "../../layouts/AppLayout";

const RESULT_BASES: { id: RecommendationBasis; label: string }[] = [
  { id: "SELF", label: "내 피부 기준" },
  { id: "POPULAR", label: "전체 인기" },
  { id: "OTHER", label: "다른 사람" },
];

/** 다른 사람 기준은 받는 사람 정보 입력 화면이 아직 없어 요청하지 않는다. */
const READY_BASES: RecommendationBasis[] = ["SELF", "POPULAR"];

const POLL_INTERVAL_MS = 1200;
const POLL_LIMIT_MS = 180_000;
const STATUS_RETRY_LIMIT = 3;

/**
 * finding: 제품명 검색 중(빠름). products: 제품명으로 찾은 목록을 보여주는 중.
 * loading/clarify/done: AI 추천 job 흐름.
 */
type Phase =
  | "idle"
  | "finding"
  | "products"
  | "loading"
  | "clarify"
  | "done"
  | "error";

interface SavedSearchView {
  baseQuery: string;
  basis: RecommendationBasis;
  jobId: string | null;
  result: QueryResult | null;
  /** 제품명 검색 결과. 있으면 AI 추천 대신 이 목록을 보여준다 */
  products?: ProductSearchItem[] | null;
  scrollTop: number;
}

// 브라우저 기록 항목마다 결과를 따로 둔다. 상세 화면에 갔다 돌아오면 다시 찾지 않는다.
const searchViews = new Map<string, SavedSearchView>();

// 개발 모드의 effect 재실행이나 연속 클릭으로 같은 추천 job 이 두 번 만들어지지 않게 한다.
// AI 가 job 마다 LLM 을 돌리므로 중복은 그대로 비용이다.
const pendingQueries = new Map<string, ReturnType<typeof requestQuery>>();
function requestQueryOnce(
  entry: string,
  query: string,
  basis: RecommendationBasis,
) {
  const key = JSON.stringify([entry, query, basis]);
  const pending = pendingQueries.get(key);
  if (pending) return pending;
  const request = requestQuery({ query, basis });
  pendingQueries.set(key, request);
  // 성공하면 잠시 뒤 지운다. 같은 화면에서 '다시 검색'은 새 job 을 만들어야 한다.
  // 실패하면 바로 지워 다음 시도가 실패한 요청을 다시 받지 않게 한다.
  request.then(
    () => setTimeout(() => pendingQueries.delete(key), 5_000),
    () => pendingQueries.delete(key),
  );
  return request;
}

function errorMessage(error: unknown, fallback: string): string {
  const code = apiErrorCode(error);
  if (code === "SKIN_PROFILE_NOT_FOUND")
    return "피부 정보가 없어서 내 피부 기준으로 찾을 수 없어요. 마이페이지에서 피부 정보를 먼저 등록해주세요.";
  if (code === "JOB_NOT_COMPLETED")
    return "이전 검색이 아직 끝나지 않았어요. 잠시 후 다시 시도해주세요.";
  if (error instanceof Error && error.message === "BUNDLE_NOT_READY")
    return "예산 세트 구성 추천은 아직 준비 중이에요. 제품 한 종류로 다시 검색해 주세요.";
  if (error instanceof Error && error.message === "TIMEOUT")
    return "분석이 오래 걸리고 있어요. 잠시 후 다시 시도해주세요.";
  return fallback;
}

/** 검색 카드가 쓰는 모양으로 바꾼다. 점수가 없으면(인기 기준) NaN 으로 두어 점수를 숨긴다. */
function toCardProduct(item: ResultItem): AiSearchProduct {
  return {
    productId: item.productId,
    name: item.name,
    brand: item.brand,
    category: "",
    imageUrl: item.imageUrl,
    originalPrice: item.price,
    matchScore: item.totalScore ?? Number.NaN,
  };
}

function rankLabel(item: ResultItem): string | null {
  switch (item.change) {
    case "NEW":
      return "새로 찾음";
    case "SAME":
      return "순위 유지";
    case "UP":
      return item.rankDelta ? `${item.rankDelta}계단 ↑` : "순위 상승";
    case "DOWN":
      return item.rankDelta ? `${Math.abs(item.rankDelta)}계단 ↓` : "순위 하락";
    default:
      return null;
  }
}

export function SearchResultPage() {
  const location = useLocation();
  return <SearchResultContent key={location.key} />;
}

function SearchResultContent() {
  const navigate = useNavigate();
  const { state, key } = useLocation() as {
    state: { query?: string } | null;
    key: string;
  };
  // ?pick=evaluate: 평가할 기준 제품을 고르는 모드. 화면은 같고, 제품을 고르면
  // 상세 대신 추천 흐름(추가 정보 → 결과)으로 간다.
  const [params] = useSearchParams();
  const picking = params.get("pick") === "evaluate";
  const cacheKey = searchViewKey(key);

  /** 제품을 골랐을 때. 일반 검색이면 상세로, 고르기 모드면 추천 흐름으로 간다. */
  function openProduct(product: {
    id: string;
    name: string;
    brand: string;
    imageUrl?: string | null;
  }) {
    recordProductView(product.id).catch(() => {});
    if (picking) {
      navigate("/recommendation/extra-info", {
        state: {
          productId: product.id,
          productName: product.name,
          productBrand: product.brand,
          productImageUrl: product.imageUrl ?? null,
        },
      });
      return;
    }
    navigate(`/product/${product.id}`);
  }
  const [saved] = useState(() => {
    const view =
      searchViews.get(cacheKey) ?? readSearchView<SavedSearchView>(cacheKey);
    if (!view || typeof view.baseQuery !== "string") return undefined;
    return view;
  });
  const initialQuery = state?.query ?? "";
  const scrollContainer = useRef<HTMLDivElement>(null);

  const [baseQuery, setBaseQuery] = useState(saved?.baseQuery ?? initialQuery);
  const [basis, setBasis] = useState<RecommendationBasis>(
    saved?.basis ?? "SELF",
  );
  const [jobId, setJobId] = useState<string | null>(saved?.jobId ?? null);
  const [result, setResult] = useState<QueryResult | null>(
    saved?.result ?? null,
  );
  const [products, setProducts] = useState<ProductSearchItem[] | null>(
    saved?.products ?? null,
  );
  const [phase, setPhase] = useState<Phase>(
    saved?.products?.length
      ? "products"
      : saved?.result
        ? "done"
        : saved?.jobId
          ? "loading"
          : "idle",
  );
  const [error, setError] = useState("");
  const [step, setStep] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [clarify, setClarify] = useState<{
    message: string;
    fields: ClarifyField[];
  } | null>(null);
  const [clarifySending, setClarifySending] = useState(false);
  const [clarifyError, setClarifyError] = useState("");

  const [sheet, setSheet] = useState<"add" | "edit" | "history" | null>(null);
  const [options, setOptions] = useState<RefinementOptions | null>(null);
  const [historyEntries, setHistoryEntries] = useState<
    RefinementHistoryEntry[]
  >([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const [feedbackTarget, setFeedbackTarget] = useState<{
    item: ResultItem;
    liked: boolean;
  } | null>(null);
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const [feedbackSent, setFeedbackSent] = useState<Record<string, true>>({});
  const [toast, setToast] = useState("");
  // 피드백으로 가중치가 바뀌었으면 알림에서 바로 되돌릴 수 있게 둔다.
  const [toastChangeId, setToastChangeId] = useState<string | null>(null);
  // 되돌린 가중치 변경. 같은 변경을 다시 되돌리지 않게 버튼을 숨긴다.
  const [revertedChanges, setRevertedChanges] = useState<Record<string, true>>({});
  const [reverting, setReverting] = useState<string | null>(null);

  /** 가중치 변경 한 건을 되돌린다. 이미 되돌린 변경(409)도 되돌린 것으로 본다. */
  async function revertChange(changeId: string) {
    setReverting(changeId);
    try {
      await revertPreferenceChange(changeId);
      setRevertedChanges((previous) => ({ ...previous, [changeId]: true }));
      setToastChangeId(null);
      setToast("되돌렸어요. 다음 추천부터 반영돼요");
    } catch (error) {
      if (apiErrorCode(error) === "CHANGE_NOT_REVERTIBLE") {
        setRevertedChanges((previous) => ({ ...previous, [changeId]: true }));
        setToastChangeId(null);
        setToast("이미 되돌린 변경이에요");
      } else {
        setToast("되돌리지 못했어요. 다시 시도해주세요.");
      }
    } finally {
      setReverting(null);
    }
  }

  // 사진·NFC로 찾기
  const lens = useProductLens(picking ? "recommend" : "detail");
  const [lensOpen, setLensOpen] = useState(false);

  // 새 요청을 시작하면 이전 폴링은 결과를 버린다.
  const version = useRef(0);
  const submitted = phase !== "idle";
  const conditions = result?.summary?.conditions ?? [];
  const items = result?.items ?? [];

  // ── 관심 상품 ─────────────────────────────────────────────────────────
  const [wishlistIds, setWishlistIds] = useState<Record<string, string> | null>(
    null,
  );
  const wishlistRequest = useRef<Promise<Record<string, string>> | null>(null);
  function loadWishlistIds() {
    if (!wishlistRequest.current) {
      wishlistRequest.current = getWishlists()
        .then(({ data }) => {
          if (!Array.isArray(data?.wishlists))
            throw new Error("INVALID_WISHLIST_RESPONSE");
          return Object.fromEntries(
            data.wishlists.map((item) => [item.product.id, item.wishlistId]),
          );
        })
        .catch((error) => {
          wishlistRequest.current = null;
          throw error;
        });
    }
    return wishlistRequest.current;
  }
  useEffect(() => {
    let active = true;
    loadWishlistIds()
      .then((ids) => {
        if (active) setWishlistIds(ids);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  async function toggleWishlist(productId: string) {
    const ids = wishlistIds ?? (await loadWishlistIds());
    const wishlistId = ids[productId];
    if (wishlistId) {
      await deleteWishlist(wishlistId);
      setWishlistIds((previous) => {
        const next = { ...(previous ?? ids) };
        delete next[productId];
        return next;
      });
    } else {
      const { data } = await addWishlist(productId);
      if (!data?.wishlistId) throw new Error("INVALID_WISHLIST_RESPONSE");
      setWishlistIds((previous) => ({
        ...(previous ?? ids),
        [productId]: data.wishlistId,
      }));
    }
  }

  // ── 처음 진입과 화면 복원 ─────────────────────────────────────────────
  useEffect(() => {
    if (!saved && initialQuery) {
      addRecentSearch(initialQuery);
      void findProducts(initialQuery);
    }
    // 진행 중에 떠났다가 돌아오면 같은 job 을 이어서 본다.
    else if (saved && !saved.result && saved.jobId)
      void follow(saved.jobId, ++version.current);
    return () => {
      version.current += 1;
    };
    // 처음 한 번만 실행한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLayoutEffect(() => {
    if (saved && scrollContainer.current)
      scrollContainer.current.scrollTop = saved.scrollTop;
  }, [saved]);

  useLayoutEffect(() => {
    if (!submitted) return;
    const view: SavedSearchView = {
      baseQuery,
      basis,
      jobId,
      result,
      products,
      scrollTop: scrollContainer.current?.scrollTop ?? 0,
    };
    searchViews.set(cacheKey, view);
    writeSearchView(cacheKey, view);
    if (searchViews.size > 20)
      searchViews.delete(searchViews.keys().next().value!);
  }, [cacheKey, submitted, baseQuery, basis, jobId, result, products]);

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

  useEffect(() => {
    if (!toast) return;
    // 되돌리기 버튼이 있으면 누를 시간을 더 준다.
    const timer = setTimeout(() => {
      setToast("");
      setToastChangeId(null);
    }, toastChangeId ? 6000 : 3000);
    return () => clearTimeout(timer);
  }, [toast, toastChangeId]);

  // ── job 흐름 ──────────────────────────────────────────────────────────
  function showResult(next: QueryResult) {
    // 결과 모양이 어긋나도 화면이 깨지지 않게 목록은 배열로 맞춘다.
    const safe = {
      ...next,
      items: Array.isArray(next?.items) ? next.items : [],
      alternatives: Array.isArray(next?.alternatives) ? next.alternatives : [],
      similarUserProducts: Array.isArray(next?.similarUserProducts)
        ? next.similarUserProducts
        : [],
    };
    setResult(safe);
    setPhase("done");
    saveLastSearch({
      query: baseQuery,
      category: safe.summary?.categoryLabel ?? "",
      products: safe.items.map(toCardProduct),
    });
  }

  /**
   * 상태를 폴링해 끝나면 결과를 보여준다. 되묻는 중이면 답변 폼을 띄운다.
   *
   * answered: 방금 되묻기에 답했다. 답을 보낸 직후 잠깐은 서버가 아직 되묻는 중으로
   * 응답하므로, 다른 상태가 한 번 보이거나 일정 시간이 지날 때까지 그 상태를 무시한다.
   */
  async function follow(nextJobId: string, current: number, answered = false) {
    setJobId(nextJobId);
    setPhase("loading");
    setClarify(null);
    setError("");
    const deadline = Date.now() + POLL_LIMIT_MS;
    let waitingForAnswer = answered;
    const answerGraceUntil = Date.now() + 15_000;
    // 상태 조회가 잠깐 실패해도 바로 오류로 끝내지 않는다. 연속으로 이만큼 실패할 때만 멈춘다.
    let statusFailures = 0;
    try {
      while (current === version.current) {
        if (Date.now() >= deadline) throw new Error("TIMEOUT");
        let data: Awaited<ReturnType<typeof getQueryStatus>>["data"];
        try {
          ({ data } = await withDeadline(getQueryStatus(nextJobId), 15_000));
          statusFailures = 0;
        } catch (error) {
          statusFailures += 1;
          if (
            statusFailures >= STATUS_RETRY_LIMIT ||
            apiErrorCode(error) === "SESSION_EXPIRED"
          )
            throw error;
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          continue;
        }
        if (current !== version.current) return;
        const now = data.steps?.find((item) => item.state === "NOW");
        setStep(data.step ?? now?.label ?? "");
        setProgress(typeof data.progress === "number" ? data.progress : null);
        if (data.status === "COMPLETED") {
          const response = await withDeadline(
            getQueryResult(nextJobId),
            15_000,
          );
          if (current !== version.current) return;
          showResult(response.data);
          return;
        }
        if (data.status !== "NEEDS_CLARIFICATION") waitingForAnswer = false;
        if (
          data.status === "NEEDS_CLARIFICATION" &&
          waitingForAnswer &&
          Date.now() < answerGraceUntil
        ) {
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          continue;
        }
        if (data.status === "NEEDS_CLARIFICATION") {
          setClarify(
            data.clarify ?? {
              message: "조금 더 구체적으로 알려주세요.",
              fields: [],
            },
          );
          setClarifyError("");
          setPhase("clarify");
          return;
        }
        if (data.status === "FAILED" && data.scenario === "S6_BUNDLE" && MOCK_UNREADY) {
          // AI 의 예산 세트 단계가 아직 없어 실패한다. 목데이터 모드에서는 예시 세트를 보여준다.
          const mock = mockBundleResult();
          setJobId(mock.jobId);
          showResult(mock);
          return;
        }
        if (data.status === "FAILED")
          throw new Error(
            data.scenario === "S6_BUNDLE" ? "BUNDLE_NOT_READY" : "FAILED",
          );
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
    } catch (error) {
      if (current !== version.current) return;
      setError(
        errorMessage(error, "추천을 완료하지 못했어요. 다시 시도해주세요."),
      );
      setPhase("error");
    }
  }

  /**
   * AI 추천을 시작한다. display 는 화면 맨 위와 조건 칩에 보일 문장이다.
   * 조건 수정처럼 보내는 문장(조건을 붙인 것)과 보여줄 문장이 다를 때 넘긴다.
   */
  async function startQuery(
    query: string,
    nextBasis: RecommendationBasis,
    display?: string,
  ) {
    const text = query.trim();
    if (!text) return;
    const current = ++version.current;
    searchViews.delete(cacheKey);
    deleteSearchView(cacheKey);
    setBaseQuery((display ?? text).trim());
    setBasis(nextBasis);
    setResult(null);
    setProducts(null);
    setJobId(null);
    setFeedbackSent({});
    setHistoryEntries([]);
    setSheet(null);
    setStep("입력하신 요청을 이해하고 있어요");
    setProgress(null);
    setError("");
    setPhase("loading");
    try {
      const { data } = await withDeadline(
        requestQueryOnce(cacheKey, text, nextBasis),
        30_000,
      );
      if (current !== version.current) return;
      await follow(data.jobId, current);
    } catch (error) {
      if (current !== version.current) return;
      setError(
        errorMessage(error, "검색을 시작하지 못했어요. 다시 시도해주세요."),
      );
      setPhase("error");
    }
  }

  /**
   * 제품명 검색을 먼저 한다. 이름으로 찾은 제품이 있으면 그 목록만 보여주고 AI 를 돌리지 않는다.
   * 내 피부에 맞는지는 제품 상세에서 확인한다. 찾은 게 없으면(문장으로 된 요청) AI 추천으로 넘어간다.
   */
  async function findProducts(query: string) {
    const text = query.trim();
    if (!text) return;
    const current = ++version.current;
    searchViews.delete(cacheKey);
    deleteSearchView(cacheKey);
    setBaseQuery(text);
    setResult(null);
    setProducts(null);
    setJobId(null);
    setSheet(null);
    setError("");
    setPhase("finding");
    let found: ProductSearchItem[] = [];
    try {
      const { data } = await withDeadline(searchProducts(text), 5_000);
      found = Array.isArray(data?.products) ? data.products : [];
    } catch {
      // 이름 검색이 실패해도 빈 목록으로 두고 AI 추천으로 이어 간다.
    }
    if (current !== version.current) return;
    if (!found.length) {
      await startQuery(text, basis === "OTHER" ? "SELF" : basis);
      return;
    }
    setProducts(found);
    setPhase("products");
    saveLastSearch({
      query: text,
      category: "",
      products: found.map((item) => ({
        productId: item.id,
        name: item.name,
        brand: item.brand,
        category: item.category,
        imageUrl: item.imageUrl ?? null,
        originalPrice: item.originalPrice ?? null,
        matchScore: Number.NaN,
      })),
    });
  }

  async function sendClarification(
    answers: Parameters<typeof answerClarification>[1],
  ) {
    if (!jobId) return;
    const current = ++version.current;
    setClarifySending(true);
    setClarifyError("");
    try {
      await answerClarification(jobId, answers);
      if (current !== version.current) return;
      setStep("답변을 반영해 다시 찾고 있어요");
      await follow(jobId, current, true);
    } catch (error) {
      if (current !== version.current) return;
      setClarifyError(
        apiErrorCode(error) === "CLARIFY_NOT_REQUIRED"
          ? "이미 답변이 반영됐어요. 결과를 다시 불러올게요."
          : "답변을 보내지 못했어요. 다시 시도해주세요.",
      );
      if (apiErrorCode(error) === "CLARIFY_NOT_REQUIRED")
        void follow(jobId, current);
    } finally {
      setClarifySending(false);
    }
  }

  async function openAddSheet() {
    setSheet("add");
    if (!jobId) return;
    try {
      const { data } = await getRefinementOptions(jobId);
      setOptions(Array.isArray(data?.presets) ? data : null);
    } catch {
      setOptions(null); // 시트는 기본 목록으로 동작한다.
    }
  }

  async function addConditions(selected: string[]) {
    if (!jobId) return;
    const presetByLabel = new Map(
      options?.presets.map((preset) => [preset.label, preset.key]),
    );
    const presetKeys: RefinePresetKey[] = [];
    const free: string[] = [];
    for (const text of selected) {
      const keyForLabel = presetByLabel.get(text) ?? DEFAULT_PRESET_KEYS[text];
      if (keyForLabel) presetKeys.push(keyForLabel);
      else free.push(text);
    }
    const current = ++version.current;
    setSheet(null);
    setFeedbackSent({});
    setStep("조건을 더해 후보를 다시 찾고 있어요");
    setProgress(null);
    setPhase("loading");
    try {
      const { data } = await requestRefinement(jobId, {
        presetKeys: presetKeys.length ? presetKeys : undefined,
        freeText: free.length ? free.join(", ").slice(0, 500) : undefined,
      });
      if (current !== version.current) return;
      await follow(data.jobId, current);
    } catch (error) {
      if (current !== version.current) return;
      setError(
        errorMessage(error, "조건을 추가하지 못했어요. 다시 시도해주세요."),
      );
      setPhase("error");
    }
  }

  /** 조건 수정은 문장을 다시 쓴 새 검색이다. 남긴 조건은 문장 뒤에 붙인다. */
  function editConditions(nextConditions: string[], editedBase?: string) {
    const base = (editedBase ?? baseQuery).trim();
    const query = nextConditions.length
      ? `${base}\n추가 조건: ${nextConditions.join(", ")}`
      : base;
    void startQuery(query, basis, base);
  }

  async function openHistory() {
    setSheet("history");
    if (!jobId) return;
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const { data } = await getRefinementHistory(jobId);
      setHistoryEntries(
        data.steps.map((item) => ({
          jobId: item.jobId,
          title: item.label,
          detail: item.detail,
          candidateCount: item.candidateCount,
        })),
      );
    } catch {
      setHistoryError("수정 이력을 불러오지 못했어요.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function restoreStep(targetJobId: string) {
    const current = ++version.current;
    setSheet(null);
    setPhase("loading");
    setStep("이전 결과를 불러오고 있어요");
    try {
      const { data } = await getQueryResult(targetJobId);
      if (current !== version.current) return;
      setJobId(targetJobId);
      setFeedbackSent({});
      showResult(data);
    } catch (error) {
      if (current !== version.current) return;
      setError(errorMessage(error, "이전 결과를 불러오지 못했어요."));
      setPhase("error");
    }
  }

  async function sendFeedback(value: FeedbackValue) {
    if (!jobId || !feedbackTarget) return;
    setFeedbackSending(true);
    setFeedbackError("");
    try {
      const { data } = await submitFeedback(jobId, {
        productId: feedbackTarget.item.productId,
        vote: value.liked ? "UP" : "DOWN",
        reasonTags:
          value.liked || !value.reasons.length ? undefined : value.reasons,
      });
      setFeedbackSent((previous) => ({
        ...previous,
        [feedbackTarget.item.productId]: true,
      }));
      setFeedbackTarget(null);
      setToastChangeId(data?.changeId ?? null);
      setToast(data?.message || "의견을 다음 추천에 반영할게요");
    } catch {
      setFeedbackError("피드백을 보내지 못했어요. 다시 시도해주세요.");
    } finally {
      setFeedbackSending(false);
    }
  }

  function changeBasis(next: RecommendationBasis) {
    if (next === basis) return;
    if (!READY_BASES.includes(next)) {
      setBasis(next);
      return;
    }
    // 기준을 바꾸면 처음 문장으로 다시 찾는다. 조건 추가로 더한 조건은 이어지지 않으니 알려준다.
    if (result?.parentJobId)
      setToast(
        "기준을 바꿔 처음 검색 문장으로 다시 찾았어요. 더한 조건은 다시 추가해 주세요.",
      );
    void startQuery(baseQuery, next);
  }

  /** 사용자가 직접 한 검색. 최근 검색어에 남긴다. */
  function search(query: string) {
    addRecentSearch(query);
    void findProducts(query);
  }

  const loading = phase === "loading";
  const ready = phase === "done" && READY_BASES.includes(basis);
  // 예산 세트 결과는 제품 목록 대신 조합을 보여준다.
  const bundleResult = ready && Boolean(result?.bundles?.length);
  // 목데이터 결과는 서버에 job 이 없어, 조건 추가·피드백처럼 job 을 쓰는 동작을 숨긴다.
  const mockResult = isMockJob(jobId);

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
          <section className="search-results-screen flex flex-col px-[18px] pb-44 pt-4 text-slate-800">
            <SearchTopBar
              value={baseQuery}
              autoFocus={!submitted}
              onBack={() => navigate(-1)}
              onSubmit={search}
              onLens={() => setLensOpen(true)}
              placeholder={
                picking ? "평가할 제품 이름을 입력하세요" : undefined
              }
              onSelectProduct={(product) => {
                addRecentSearch(product.name);
                openProduct(product);
              }}
            />
            {picking && (
              <p className="mt-3 rounded-xl bg-primary-50 px-3.5 py-2.5 text-xs leading-5 text-primary-600">
                <span className="font-semibold">평가할 제품을 골라주세요.</span>{" "}
                고른 제품이 내 피부에 맞는지, 더 나은 대체 제품이 있는지 분석해
                드려요.
              </p>
            )}

            {(phase === "done" || phase === "error") && (
              <div
                role="tablist"
                aria-label="검색 결과 기준"
                className="mt-4 grid grid-cols-3 gap-1 rounded-xl bg-surface-tint p-1"
              >
                {RESULT_BASES.map((item, index) => (
                  <button
                    key={item.id}
  // "이 제품 어때?"는 목록 대신 평가한 제품 하나의 보고서를 보여준다.
  const evaluation = ready && result?.scenario === "S1_EVALUATE" && items.length > 0;
                    id={`basis-tab-${item.id}`}
                    type="button"
                    role="tab"
                    aria-selected={basis === item.id}
                    aria-controls="basis-results"
                    tabIndex={basis === item.id ? 0 : -1}
                    onClick={() => changeBasis(item.id)}
                    onKeyDown={(event) => {
                      const next =
                        event.key === "ArrowRight"
                          ? (index + 1) % RESULT_BASES.length
                          : event.key === "ArrowLeft"
                            ? (index + RESULT_BASES.length - 1) %
                              RESULT_BASES.length
                            : null;
                      if (next != null) {
                        event.preventDefault();
                        document
                          .getElementById(`basis-tab-${RESULT_BASES[next].id}`)
                          ?.focus();
                      }
                    }}
                    className={`min-h-10 rounded-lg px-1 text-xs font-semibold transition-colors ${basis === item.id ? "bg-primary-200 text-primary-900" : "text-slate-500 hover:bg-white/60"}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}

            {!submitted && (
              <SearchEntry
                onSearch={search}
                onPhoto={() => setLensOpen(true)}
                onNfc={lens.openNfc}
                nfcSupported={lens.nfcSupported}
              />
            )}

            {ready && (
              <section
                aria-label="검색 조건"
                className="mt-2 border-b border-slate-100 pb-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">현재 조건</p>
                  <button
                    type="button"
                    onClick={() => setSheet("edit")}
                    className="flex min-h-10 items-center text-xs text-primary-600"
                  >
                    조건 수정{" "}
                    <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {[baseQuery, ...conditions].map((condition, index) => (
                    <span
                      key={`${index}-${condition}`}
                      className="max-w-full break-words rounded-md bg-surface-tint px-2.5 py-1.5 text-[11px] leading-4 text-slate-600"
                    >
                      {condition}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {loading && (
              <SearchAnalysisLoading
                searching={false}
                step={step}
                progress={progress}
              />
            )}

            {phase === "finding" && (
              <p
                role="status"
                className="mt-10 text-center text-caption text-slate-500"
              >
                제품을 찾고 있어요
              </p>
            )}

            {phase === "products" && products && (
              <section aria-labelledby="found-products-title" className="mt-5">
                <div className="flex items-end justify-between gap-2">
                  <h2
                    id="found-products-title"
                    className="text-base font-semibold text-slate-800"
                  >
                    검색한 제품
                  </h2>
                  <span className="text-xs text-slate-500">
                    {products.length}개
                  </span>
                </div>
                {!picking && (
                  <button
                    type="button"
                    onClick={() => void startQuery(baseQuery, "SELF")}
                    className="mt-3 flex w-full items-center gap-3 rounded-2xl bg-surface-tint p-3.5 text-left"
                  >
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-primary-600">
                      <Sparkles aria-hidden="true" className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-caption font-semibold text-slate-800">
                        내 피부에 맞게 AI 추천받기
                      </span>
                      <span className="mt-0.5 block text-[11px] text-slate-500">
                        ‘{baseQuery}’로 피부 정보와 후기를 함께 비교해요
                      </span>
                    </span>
                    <ChevronRight
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0 text-slate-400"
                    />
                  </button>
                )}
                <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-5">
                  {products.map((item, index) => (
                    <SearchProductCard
                      key={item.id}
                      product={{
                        productId: item.id,
                        name: item.name,
                        brand: item.brand,
                        category: item.category,
                        imageUrl: item.imageUrl ?? null,
                        originalPrice: item.originalPrice ?? null,
                        matchScore: Number.NaN,
                      }}
                      rank={index + 1}
                      rankLabel={null}
                      showScore={false}
                      saved={Boolean(wishlistIds?.[item.id])}
                      onToggleSaved={() => toggleWishlist(item.id)}
                      onOpen={() => openProduct(item)}
                    />
                  ))}
                </div>
              </section>
            )}

            {phase === "clarify" && clarify && (
              <ClarifyForm
                message={clarify.message}
                fields={clarify.fields}
                submitting={clarifySending}
                error={clarifyError}
                onSubmit={(answers) => void sendClarification(answers)}
              />
            )}

            {phase === "error" && (
              <div role="alert" className="mt-8 text-center">
                <p className="text-body2 leading-6 text-gray-400">{error}</p>
                <button
                  type="button"
                  onClick={() =>
                    void startQuery(
                      baseQuery,
                      READY_BASES.includes(basis) ? basis : "SELF",
                    )
                  }
                  className="mt-3 min-h-10 text-caption font-semibold text-primary-600"
                >
                  다시 검색
                </button>
              </div>
            )}

            {phase === "done" && (
              <div
                id="basis-results"
                role="tabpanel"
                aria-labelledby={`basis-tab-${basis}`}
              >
                {!READY_BASES.includes(basis) && (
                  <div className="px-4 py-14 text-center">
                    <p className="text-sm font-semibold text-gray-500">
                      다른 사람 기준 검색을 준비하고 있어요
                    </p>
                    <p className="mt-2 text-xs leading-5 text-gray-300">
                      받는 분의 피부 정보를 입력하는 화면이 아직 없어요.
                    </p>
                    <button
                      type="button"
                      onClick={() => setBasis(result?.basis ?? "SELF")}
                      className="mt-4 min-h-10 rounded-lg bg-primary-50 px-4 text-xs font-semibold text-primary-600"
                    >
                      현재 검색 결과 보기
                    </button>
                  </div>
                )}
                {ready && result?.summary?.notice && (
                  <p className="mt-4 rounded-xl bg-primary-50 p-3 text-[11px] leading-5 text-primary-600">
                    {result.summary.notice}
                  </p>
                )}
                {ready && result?.appliedPreference?.text && (() => {
                  const changeId = result.appliedPreference.changeId;
                  const reverted = changeId != null && revertedChanges[changeId];
                  return (
                    <div className="mt-2 flex items-start justify-between gap-3 text-[11px] leading-5 text-slate-500">
                      <p>
                        {reverted
                          ? "이 조건은 되돌렸어요. 다음 추천부터 빠져요."
                          : result.appliedPreference.text}
                      </p>
                      {changeId && !reverted && !mockResult && (
                        <button
                          type="button"
                          onClick={() => void revertChange(changeId)}
                          disabled={reverting === changeId}
                          className="flex min-h-8 shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2 text-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Undo2 aria-hidden="true" className="h-3.5 w-3.5" />
                          {reverting === changeId ? "되돌리는 중" : "되돌리기"}
                        </button>
                      )}
                    </div>
                  );
                })()}
                {evaluation && (
                  <EvaluationReport
                    item={items[0]}
                    onOpen={() =>
                      openProduct({
                        id: items[0].productId,
                        name: items[0].name,
                        brand: items[0].brand,
                        imageUrl: items[0].imageUrl,
                      })
                    }
                  />
                )}
                {ready && items.length > 0 && !evaluation && (
                  <>
                    <div className="mt-5 flex items-center justify-between gap-2">
                      <div>
                        <h2 className="mb-1 text-base font-semibold text-slate-800">
                          요청에 맞는 제품
                        </h2>
                        <p className="flex gap-2 text-xs leading-5 text-slate-500">
                          {result?.summary?.categoryLabel && (
                            <span>{result.summary.categoryLabel}</span>
                          )}
                          <span>{items.length}개 결과</span>
                        </p>
                      </div>
                      {result?.summary?.basisLabel && (
                        <span className="text-xs text-slate-500">
                          {result.summary.basisLabel}
                        </span>
                      )}
                    </div>
                    {result?.excluded && result.excluded.count > 0 && (
                      <p className="mt-1 text-[11px] text-slate-500">
                        보유 제품과 겹치거나 함께 쓰기 어려운 제품{" "}
                        {result.excluded.count}개는 뺐어요
                      </p>
                    )}
                    <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-5">
                      {items.map((item, index) => (
                        <SearchProductCard
                          key={item.productId}
                          product={toCardProduct(item)}
                          rank={index + 1}
                          rankLabel={rankLabel(item)}
                          personalization={item.totalScore}
                          rating={item.rating}
                          reviewCount={item.reviewCount}
                          reason={item.reason}
                          feedbackSent={Boolean(feedbackSent[item.productId])}
                          saved={Boolean(wishlistIds?.[item.productId])}
                          onToggleSaved={() => toggleWishlist(item.productId)}
                          onFeedback={() => {
                            setFeedbackError("");
                            setFeedbackTarget({ item, liked: true });
                          }}
                          onOpen={() =>
                            openProduct({
                              id: item.productId,
                              name: item.name,
                              brand: item.brand,
                              imageUrl: item.imageUrl,
                            })
                          }
                        />
                      ))}
                    </div>
                  </>
                )}
                {bundleResult && result?.bundles && jobId && (
                  <BundleResult
                    jobId={jobId}
                    bundles={result.bundles}
                    onChange={(updated) =>
                      setResult((previous) =>
                        previous
                          ? {
                              ...previous,
                              bundles: (previous.bundles ?? []).map((b) =>
                                b.index === updated.index ? updated : b,
                              ),
                            }
                          : previous,
                      )
                    }
                  />
                )}
                {ready && !items.length && !bundleResult && (
                  <div className="mt-12 text-center">
                    <p className="text-body2 text-gray-400">
                      검색 결과가 없어요
                    </p>
                    <p className="mt-2 text-caption text-gray-300">
                      조건을 수정하거나 다른 표현으로 다시 검색해 보세요
                    </p>
                  </div>
                )}
                {ready && result && (
                  <>
                    {/* 화담의 핵심: 피부 타입·고민이 비슷한 사람들이 실제로 쓰는 제품 */}
                    <RelatedProductRow
                      icon={UsersRound}
                      title="나와 비슷한 사람들이 쓰는 제품"
                      description="피부 타입과 고민이 비슷한 분들이 만족한 제품이에요"
                      products={(result.similarUserProducts ?? []).map((p) => ({
                        productId: p.productId,
                        name: p.name,
                        brand: p.brand,
                        price: p.price,
                      }))}
                      onOpen={(p) =>
                        openProduct({ id: p.productId, name: p.name, brand: p.brand })
                      }
                    />
                    <RelatedProductRow
                      icon={Shuffle}
                      title="비슷한 대체 제품"
                      description={
                        result.alternativesDroppedCount > 0
                          ? `기준에 못 미친 후보 ${result.alternativesDroppedCount}개는 뺐어요`
                          : "성분과 특징이 비슷한 다른 선택지예요"
                      }
                      products={(result.alternatives ?? []).map((p) => ({
                        productId: p.productId,
                        name: p.name,
                        brand: p.brand,
                        price: p.price,
                        tag:
                          p.similarity != null
                            ? `유사도 ${Math.round(p.similarity * 100)}%`
                            : p.totalScore != null
                              ? `적합 ${p.totalScore}점`
                              : null,
                      }))}
                      onOpen={(p) =>
                        openProduct({ id: p.productId, name: p.name, brand: p.brand })
                      }
                    />
                  </>
                )}
              </div>
            )}
          </section>
        </div>
      </div>

      {ready && !mockResult && (
        <div
          className="pointer-events-none fixed bottom-[88px] left-1/2 z-30 flex w-full max-w-[430px] -translate-x-1/2 items-center gap-3 px-[18px]"
          style={{ marginBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          {(result?.parentJobId || historyEntries.length > 1) && (
            <button
              type="button"
              onClick={() => void openHistory()}
              className="pointer-events-auto flex min-h-11 items-center gap-1.5 rounded-[14px] border border-slate-200 bg-white px-3 text-xs text-slate-600 shadow-tint-md"
            >
              <History aria-hidden="true" className="h-4 w-4" /> 수정 이력
            </button>
          )}
          <button
            type="button"
            onClick={() => void openAddSheet()}
            className="pointer-events-auto ml-auto flex min-h-12 items-center gap-1.5 rounded-[14px] bg-primary-200 px-4 text-[13px] font-semibold text-primary-900 shadow-tint-lg"
          >
            <Plus aria-hidden="true" className="h-[18px] w-[18px]" /> 조건 추가
          </button>
        </div>
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-[150px] left-1/2 z-40 flex w-[calc(100%-36px)] max-w-[394px] -translate-x-1/2 items-center justify-between gap-3 rounded-xl bg-slate-800/90 px-4 py-3 text-xs text-white"
        >
          <span className={toastChangeId ? "" : "w-full text-center"}>{toast}</span>
          {toastChangeId && !revertedChanges[toastChangeId] && (
            <button
              type="button"
              onClick={() => void revertChange(toastChangeId)}
              disabled={reverting === toastChangeId}
              className="flex min-h-8 shrink-0 items-center gap-1 font-semibold text-primary-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Undo2 aria-hidden="true" className="h-3.5 w-3.5" />
              되돌리기
            </button>
          )}
        </div>
      )}

      <BottomNav compactSearch />

      {lens.inputs}
      {lensOpen && (
        <ProductLensSheet
          nfcSupported={lens.nfcSupported}
          onCamera={lens.openCamera}
          onAlbum={lens.openAlbum}
          onNfc={lens.openNfc}
          onClose={() => setLensOpen(false)}
        />
      )}
      {lens.recognizing && (
        <div
          role="status"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 px-8"
        >
          <div className="w-full max-w-[300px] rounded-2xl bg-white p-6 text-center">
            <div className="mx-auto h-9 w-9 motion-safe:animate-spin rounded-full border-[3px] border-primary-100 border-t-primary-500" />
            <p className="mt-4 text-body2 font-semibold text-slate-800">
              사진 속 제품을 찾고 있어요
            </p>
            <p className="mt-1 text-caption text-slate-500">
              몇 초 정도 걸려요
            </p>
          </div>
        </div>
      )}
      {lens.error && (
        <div
          role="alert"
          className="fixed bottom-[150px] left-1/2 z-40 flex w-[calc(100%-36px)] max-w-[394px] -translate-x-1/2 items-center gap-2 rounded-xl bg-slate-800/90 px-4 py-3 text-xs text-white"
        >
          <span className="flex-1">{lens.error}</span>
          <button
            type="button"
            onClick={lens.clearError}
            className="shrink-0 font-semibold"
          >
            닫기
          </button>
        </div>
      )}

      {(sheet === "add" || sheet === "edit") && (
        <RecommendationRefinementSheet
          key={sheet}
          mode={sheet}
          baseQuery={baseQuery}
          conditions={conditions}
          options={
            sheet === "add" && options?.presets.length
              ? options.presets.map(({ label, frequent }) => ({
                  label,
                  frequent,
                }))
              : undefined
          }
          onClose={() => setSheet(null)}
          onApply={(selected, editedBase) =>
            sheet === "add"
              ? void addConditions(selected)
              : editConditions(selected, editedBase)
          }
        />
      )}
      {sheet === "history" && (
        <RefinementHistorySheet
          entries={historyEntries}
          activeJobId={jobId}
          loading={historyLoading}
          error={historyError}
          onClose={() => setSheet(null)}
          onSelect={(target) => void restoreStep(target)}
        />
      )}
      {feedbackTarget && (
        <RecommendationFeedbackSheet
          product={{
            name: feedbackTarget.item.name,
            brand: feedbackTarget.item.brand,
            imageUrl: feedbackTarget.item.imageUrl,
            price: feedbackTarget.item.price,
            score: feedbackTarget.item.totalScore,
          }}
          initialLiked={feedbackTarget.liked}
          submitting={feedbackSending}
          error={feedbackError}
          onClose={() => setFeedbackTarget(null)}
          onSubmit={(value) => void sendFeedback(value)}
        />
      )}
    </AppLayout>
  );
}

/** refinement-options 를 못 받았을 때 기본 칩 이름으로 키를 찾는다. 서버 enum 의 label 과 같다. */
const DEFAULT_PRESET_KEYS: Record<string, RefinePresetKey> = {
  "더 저렴하게": "CHEAPER",
  "향 없는 걸로": "UNSCENTED",
  "커버력 높게": "HIGH_COVERAGE",
  "지속력 좋은": "LONG_LASTING",
  "자외선 차단": "UV_PROTECT",
  "민감성도 괜찮은": "SENSITIVE_OK",
};
