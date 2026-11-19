import type { AiSearchProduct, AiSearchResponse } from "../api/productApi";
import { getAccessToken } from "./auth";

const SEARCH_HISTORY_KEY = "bm_last_search";
const MAX_RECENTLY_VIEWED = 10;

// ── 마지막 AI 검색 결과 캐시 ──────────────────────────────────────────────────

export interface LastSearch {
  query: string;
  category: string;
  intent?: AiSearchResponse["intent"];
  products: AiSearchProduct[];  // 상위 5개만 저장
  searchedAt: string;
}

export function saveLastSearch(data: Omit<LastSearch, "searchedAt">) {
  const entry: LastSearch = {
    ...data,
    products: data.products.slice(0, 5),
    searchedAt: new Date().toISOString(),
  };
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(entry));
}

export function getLastSearch(): LastSearch | null {
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
    return raw ? (JSON.parse(raw) as LastSearch) : null;
  } catch {
    return null;
  }
}

// ── 최근 검색어 ───────────────────────────────────────────────────────────────
// 한 기기를 여러 계정이 쓸 수 있어 계정(sub)별로 나눠 저장한다.

const RECENT_SEARCHES_PREFIX = "hwadam.recent-searches:";
const MAX_RECENT_SEARCHES = 10;

function recentSearchesKey(): string {
  let owner = "anonymous";
  try {
    const token = getAccessToken() ?? "";
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(payload));
    if (typeof claims.sub === "string") owner = claims.sub;
  } catch {
    /* 토큰이 없거나 형식이 다르면 익명으로 둔다. */
  }
  return RECENT_SEARCHES_PREFIX + owner;
}

export function getRecentSearches(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(recentSearchesKey()) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function writeRecentSearches(list: string[]) {
  try {
    localStorage.setItem(recentSearchesKey(), JSON.stringify(list));
  } catch {
    /* 저장소를 못 쓰면 기록 없이 동작한다. */
  }
}

/** 맨 앞에 넣는다. 같은 검색어는 앞으로 옮긴다. */
export function addRecentSearch(query: string): string[] {
  const text = query.trim();
  if (!text) return getRecentSearches();
  const next = [text, ...getRecentSearches().filter((item) => item !== text)].slice(
    0,
    MAX_RECENT_SEARCHES,
  );
  writeRecentSearches(next);
  return next;
}

export function removeRecentSearch(query: string): string[] {
  const next = getRecentSearches().filter((item) => item !== query);
  writeRecentSearches(next);
  return next;
}

export function clearRecentSearches(): string[] {
  writeRecentSearches([]);
  return [];
}

// ── 최근 본 상품 (클라이언트 사이드 보조 캐시) ────────────────────────────────
// BE의 recently-viewed API가 기준이지만, 오프라인/빠른 렌더링용으로도 사용

export interface ViewedProduct {
  productId: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
  viewedAt: string;
}

export function saveViewedProduct(product: Omit<ViewedProduct, "viewedAt">) {
  const list = getViewedProducts().filter((p) => p.productId !== product.productId);
  const entry: ViewedProduct = { ...product, viewedAt: new Date().toISOString() };
  const updated = [entry, ...list].slice(0, MAX_RECENTLY_VIEWED);
  localStorage.setItem("bm_recently_viewed", JSON.stringify(updated));
}

export function getViewedProducts(): ViewedProduct[] {
  try {
    const raw = localStorage.getItem("bm_recently_viewed");
    return raw ? (JSON.parse(raw) as ViewedProduct[]) : [];
  } catch {
    return [];
  }
}
