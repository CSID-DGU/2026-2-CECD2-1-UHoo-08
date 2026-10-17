import { api } from "../lib/api";

import { getAccessToken } from "../lib/auth";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface StoreInfo {
  storeName: string;
  price: number;
  isLowest: boolean;
}

export interface ProductDetail {
  productId: string;
  name: string;
  brand: string;
  category: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  lowestPrice: number | null;
  featureJson: unknown;
  reviewSummary: string | null;
  averageScore: number | null;
  reviewCount: number | null;
  stores: StoreInfo[] | null;
  wishlisted: boolean;
  wishlistId: string | null;
}

export const getProductDetail = (productId: string) =>
  api.get<ApiResponse<ProductDetail>>(`/products/${productId}`);

export interface RecognizeResult {
  productId: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
}

export interface ProductSearchItem {
  id: string;
  name: string;
  brand: string;
  category: string;
  imageUrl?: string | null;
  originalPrice?: number | null;
}

export const recognizeProduct = (type: "IMAGE" | "TEXT" | "NFC", data: string) =>
  api.post<ApiResponse<RecognizeResult>>("/products/recognize", { type, data });

export const searchProducts = (keyword: string) =>
  api.get<ApiResponse<{ products: ProductSearchItem[] }>>(
    `/products/search?keyword=${encodeURIComponent(keyword)}`,
  );

export const recordProductView = (productId: string) =>
  api.post<ApiResponse<null>>(`/products/${productId}/view`);

export const getRecentlyViewed = (limit = 10) =>
  api.get<ApiResponse<{ products: ProductSearchItem[] }>>(
    `/products/recently-viewed?limit=${limit}`,
  );

export interface SimilarUserProduct {
  id: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
  originalPrice?: number | null;
  satisfactionPercent?: number | null;
}

export const getSimilarUserProducts = (limit = 10) =>
  api.get<ApiResponse<{ products: SimilarUserProduct[] }>>(
    `/products/similar-users?limit=${limit}`,
  );

// ── AI 자연어 검색 (FastAPI) ─────────────────────────────────────────────────

export interface AiSearchProduct {
  productId: string;
  name: string;
  brand: string;
  category: string;
  imageUrl?: string | null;
  originalPrice?: number | null;
  matchScore: number;
}

export interface AiSearchResponse {
  query: string;
  category: string;
  /** 현재 BE에서는 생략될 수 있어, 없으면 제품 목록을 중립적으로 표시한다. */
  intent?: "PRODUCT_NAME" | "RECOMMENDATION" | "PURCHASE_DECISION";
  products: AiSearchProduct[];
}

const pendingSearches = new Map<string, Promise<AiSearchResponse>>();

export function aiSearch(query: string): Promise<AiSearchResponse> {
  const normalizedQuery = query.trim();
  const key = JSON.stringify([getAccessToken(), normalizedQuery]);
  const pending = pendingSearches.get(key);
  if (pending) return pending;

  // 개발 모드의 effect 재실행·연속 클릭으로 같은 AI 작업이 중복 생성되지 않게 한다.
  const request = api.post<{ success: boolean; data: AiSearchResponse }>(
    "/recommendations/search", { query: normalizedQuery },
  ).then((res) => res.data).finally(() => pendingSearches.delete(key));
  pendingSearches.set(key, request);
  return request;
}

// ── AI 제품 인식 (FastAPI /internal/recognize) ────────────────────────────────

export interface AiRecognizeResult {
  productId: string | null;
  name: string | null;
  brand: string | null;
  category: string | null;
  geminiPrice: Record<string, unknown>;
  reviewSummary: Record<string, unknown>;
  ingredients: string[];
}

export const aiRecognizeProduct = (
  type: "IMAGE" | "TEXT" | "NFC",
  data: string,
): Promise<AiRecognizeResult> =>
  api.post<AiRecognizeResult>("/ai/internal/recognize", { type, data });
