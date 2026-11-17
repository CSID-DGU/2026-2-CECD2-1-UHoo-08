import { api } from "../lib/api";

/**
 * 보유 제품 API (BE).
 *
 * AI CARE(`myProductApi.ts`)와 같은 user_products 테이블을 쓴다. 그래서 여기서 등록한
 * 제품도 키오스크와 홈 카드에 그대로 보인다.
 *
 * BE 는 보관 위치를 받지 않는다. 보관 위치는 AI CARE 의 수정 API 로 같은 행에 넣는다.
 */

interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: { page: number; size: number; total: number };
}

export type UserProductStatus = "USING" | "FINISHED" | "DISCARDED";

export interface UserProductItem {
  userProductId: string;
  productId: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  openedAt: string | null;
  remainingPct: number | null;
  /** OK, SOON(45일 이내), EXPIRED */
  replaceStatus: "OK" | "SOON" | "EXPIRED" | null;
  replaceText: string | null;
  /** 교체 시기까지 막대 길이 0~100 */
  replaceProgress: number;
  conflictText: string | null;
}

export interface UserProductList {
  items: UserProductItem[];
  conflictSummary: { avoidCount: number; text: string | null } | null;
}

export interface UserProductCreated {
  userProductId: string;
  productId: string;
  name: string;
  /** 이미 쓰는 제품과 충돌하는 조합. 확인에 실패하면 빈 배열 */
  conflicts: { userProductId: string; name: string; level: "SEPARATE" | "AVOID"; advice: string | null }[];
}

export const getUserProducts = (status: UserProductStatus | "ALL" = "USING") =>
  api.get<ApiResponse<UserProductList>>(`/user-products?status=${status}&sort=REPLACE_NEED&size=50`);

/** openedAt 을 빼면 서버가 오늘로 기록한다. */
export const createUserProduct = (body: {
  productId: string;
  openedAt?: string;
  remainingPct: number;
  source: "MANUAL";
}) => api.post<ApiResponse<UserProductCreated>>("/user-products", body);

export const updateUserProduct = (
  userProductId: string,
  body: {
    remainingPct?: number;
    status?: UserProductStatus;
    finishedAt?: string;
    openedAt?: string;
  },
) =>
  api.patch<ApiResponse<{ userProductId: string; status: UserProductStatus; remainingPct: number | null }>>(
    `/user-products/${userProductId}`,
    body,
  );

export const deleteUserProduct = (userProductId: string) =>
  api.delete<ApiResponse<{ userProductId: string }>>(`/user-products/${userProductId}`);

/**
 * 개봉일 입력값("YYYY-MM" 또는 "YYYY-MM-DD")을 BE 가 받는 날짜로 바꾼다.
 * 일을 모르면 그 달 15일로 둔다(AI CARE 가 월만 받을 때 쓰는 것과 같은 기준).
 */
export function toServerDate(value: string): string {
  return /^\d{4}-\d{2}$/.test(value) ? `${value}-15` : value;
}
