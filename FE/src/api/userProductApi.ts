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

/** 서버가 한 번에 주는 최대 개수(MAX_PAGE_SIZE). */
const PAGE_SIZE = 100;

/** 응답 모양이 다르면 요청 오류로 돌린다. 화면은 기존 실패 처리로 받는다. */
function invalid(what: string): never {
  throw { success: false, error: { code: "INVALID_RESPONSE", message: what, status: 0 } };
}

export const getUserProducts = async (status: UserProductStatus | "ALL" = "USING", page = 1) => {
  const response = await api.get<ApiResponse<UserProductList>>(
    `/user-products?status=${status}&sort=REPLACE_NEED&page=${page}&size=${PAGE_SIZE}`,
  );
  if (!Array.isArray(response?.data?.items)) invalid("user-products items");
  return response;
};

/**
 * 목록 전체. 첫 쪽을 받은 뒤 meta.total 만큼 나머지 쪽을 이어서 받는다.
 * 첫 쪽이 오면 onFirstPage 로 먼저 알려, 나머지를 받는 동안에도 화면을 쓸 수 있게 한다.
 */
export async function getAllUserProducts(
  status: UserProductStatus | "ALL",
  onFirstPage?: (list: UserProductList) => void,
): Promise<UserProductList> {
  const first = await getUserProducts(status, 1);
  const total = first.meta?.total ?? first.data.items.length;
  const pages = Math.ceil(total / PAGE_SIZE);
  if (pages <= 1) return first.data;
  onFirstPage?.(first.data);
  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, index) => getUserProducts(status, index + 2)),
  );
  return { ...first.data, items: [first.data.items, ...rest.map((r) => r.data.items)].flat() };
}

/** openedAt 을 빼면 서버가 오늘로 기록한다. */
export const createUserProduct = async (body: {
  productId: string;
  openedAt?: string;
  remainingPct: number;
  source: "MANUAL";
}) => {
  const response = await api.post<ApiResponse<UserProductCreated>>("/user-products", body);
  if (!response?.data?.userProductId) invalid("user-products create");
  // 충돌 확인에 실패하면 서버가 빈 배열을 준다. 모양이 다르면 충돌 없음으로 둔다.
  if (!Array.isArray(response.data.conflicts)) response.data.conflicts = [];
  return response;
};

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
