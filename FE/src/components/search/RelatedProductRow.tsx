import type { LucideIcon } from "lucide-react";
import { ProductThumbnail } from "../common/ProductThumbnail";

export interface RelatedProduct {
  productId: string;
  name: string;
  brand: string;
  price: number | null;
  /** 카드 아래 작은 표시. 예: "유사도 82%" */
  tag?: string | null;
}

/**
 * 추천 결과 아래의 가로 목록. 비슷한 사람들이 쓰는 제품, 대체 상품처럼
 * 본 결과를 보완하는 목록에 쓴다. BE 가 이미지를 주지 않아 그림 대신 제품 모양 표시를 둔다.
 */
export function RelatedProductRow({
  icon: Icon,
  title,
  description,
  products,
  onOpen,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  products: RelatedProduct[];
  onOpen: (product: RelatedProduct) => void;
}) {
  if (!products.length) return null;
  return (
    <section className="mt-8" aria-label={title}>
      <div className="flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-[#F2F6FC] text-[#2C507D]">
          <Icon aria-hidden="true" className="h-4 w-4" strokeWidth={1.9} />
        </span>
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      </div>
      {description && <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>}
      <ul className="-mx-[18px] mt-3 flex gap-3 overflow-x-auto px-[18px] pb-1 scrollbar-none">
        {products.map((product) => (
          <li key={product.productId} className="w-[132px] shrink-0">
            <button
              type="button"
              onClick={() => onOpen(product)}
              className="block w-full rounded-2xl border border-slate-100 bg-white p-2.5 text-left"
            >
              <ProductThumbnail
                className="aspect-square w-full rounded-xl bg-[#F2F6FC]"
                shape={product.name.includes("쿠션") ? "cushion" : "bottle"}
              />
              <p className="mt-2 truncate text-[10px] text-slate-500">{product.brand}</p>
              <p className="line-clamp-2 min-h-8 text-[11px] font-medium leading-4 text-slate-800">{product.name}</p>
              <div className="mt-1.5 flex items-center justify-between gap-1">
                <span className="text-[11px] font-semibold tabular-nums text-slate-800">
                  {product.price != null ? `${product.price.toLocaleString("ko-KR")}원` : "가격 정보 없음"}
                </span>
              </div>
              {product.tag && (
                <span className="mt-1.5 inline-block rounded-md bg-primary-50 px-1.5 py-0.5 text-[10px] text-primary-600">
                  {product.tag}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
