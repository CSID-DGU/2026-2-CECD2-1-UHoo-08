import { api } from "../lib/api";
import type { QueryResult } from "./recommendationQueryApi";

/**
 * 홈·생활 환경 API (BE).
 *
 * 환경 요약과 환경 맞춤 추천은 지역이 저장돼 있어야 한다. 없으면 404 REGION_NOT_SET 이 온다.
 * 지역은 시·도 단위다(regionCode). regionName 은 화면에 보여 줄 이름이다.
 */

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

/** BE 가 받는 시·도 이름. 광주와 전남은 하나로 다룬다. */
export const REGION_CODES = [
  "서울", "부산", "대구", "인천", "대전", "울산", "세종", "경기",
  "강원", "충북", "충남", "전북", "전남광주", "경북", "경남", "제주",
] as const;

export type EnvMetric = "UV" | "PM" | "HUMIDITY" | "TEMP";

export interface EnvironmentCondition {
  /** UV_PROTECT, SOOTHING, BARRIER */
  key: string;
  label: string;
  basis: string | null;
  covered: boolean;
  coveredBy: string | null;
}

export interface EnvironmentSummary {
  regionName: string;
  periodStart: string;
  periodEnd: string;
  dayCount: number;
  stats: { uvHighDays: number; dustBadDays: number; avgHumidity: number | null } | null;
  seasonChange: { title: string; message: string } | null;
  recommendationAvailable: boolean;
  conditions: EnvironmentCondition[];
  missingCount: number;
  updatedAt: string | null;
}

export interface EnvironmentDaily {
  metric: EnvMetric;
  label: string;
  headline: string | null;
  subText: string | null;
  threshold: number | null;
  days: { date: string; value: number | null; exceeded: boolean }[];
}

export interface EnvironmentRecommendation {
  state: "READY" | "FULLY_COVERED" | "NOT_READY";
  missingConditions: { key: string; label: string }[];
  coveredConditions: { key: string; label: string; coveredBy: string | null }[];
  result: QueryResult | null;
  computedAt: string | null;
}

export interface RoutineCheck {
  /** false 면 아직 점검 전이라 쌍과 개수가 비어 있다 */
  checked: boolean;
  productCount: number;
  counts: { ok: number; separate: number; avoid: number };
  pairs: {
    a: { userProductId: string; name: string };
    b: { userProductId: string; name: string };
    level: "OK" | "SEPARATE" | "AVOID";
    title: string | null;
    reason: string | null;
  }[];
  replacement: {
    replaceTarget: { userProductId: string; name: string };
    message: string | null;
    items: { productId: string; name: string; brand: string; price: number | null; badge: string | null }[];
  } | null;
  schedule: { morning: string[]; evening: string[]; tip: string | null } | null;
  uncomparedCount: number;
}

export interface TrendProducts {
  periodDays: number;
  items: {
    rank: number;
    productId: string;
    name: string;
    brand: string;
    price: number | null;
    imageUrl: string | null;
    interestChangePct: number | null;
  }[];
  updatedAt: string | null;
}

export interface ProductCompatibility {
  level: "OK" | "SEPARATE" | "AVOID";
  /** OK 면 null */
  bannerText: string | null;
  pairs: {
    userProductId: string;
    userProductName: string;
    ingredientA: string;
    ingredientB: string;
    level: "SEPARATE" | "AVOID";
    title: string;
    reason: string;
    schedule: { morning: string | null; evening: string | null; tip: string | null } | null;
  }[];
  basis: string[];
}

export const updateRegion = (regionCode: string, regionName: string) =>
  api.patch<ApiResponse<{ regionCode: string; regionName: string }>>("/users/me/region", {
    regionCode,
    regionName,
  });

export const getEnvironmentSummary = () =>
  api.get<ApiResponse<EnvironmentSummary>>("/environment/summary");

export const getEnvironmentDaily = (metric: EnvMetric, days = 28) =>
  api.get<ApiResponse<EnvironmentDaily>>(`/environment/daily?metric=${metric}&days=${days}`);

export const getHomeEnvironmentRecommendation = () =>
  api.get<ApiResponse<EnvironmentRecommendation>>("/home/recommendations/environment");

export const getRoutineCheck = () => api.get<ApiResponse<RoutineCheck>>("/home/routine-check");

export const getTrendProducts = () => api.get<ApiResponse<TrendProducts>>("/trends/products");

export const getProductCompatibility = (productId: string) =>
  api.get<ApiResponse<ProductCompatibility>>(`/products/${productId}/compatibility`);
