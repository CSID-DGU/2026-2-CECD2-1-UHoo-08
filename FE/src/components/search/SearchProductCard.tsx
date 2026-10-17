import { useRef, useState } from "react";
import { Heart } from "lucide-react";
import type { AiSearchProduct } from "../../api/productApi";
import { ProductThumbnail } from "../common/ProductThumbnail";

export function SearchProductCard({ product, rank, rankLabel, personalization, saved, onOpen, onToggleSaved }: {
  product: AiSearchProduct;
  rank: number;
  rankLabel: string | null;
  personalization?: number | null;
  saved: boolean;
  onOpen: () => void;
  onToggleSaved: () => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const score = Number.isFinite(personalization) ? personalization : Number.isFinite(product.matchScore) ? product.matchScore : null;
  const personal = Number.isFinite(personalization);
  async function toggleSaved() {
    if (submitting.current) return;
    submitting.current = true;
    setPending(true); setError("");
    try { await onToggleSaved(); }
    catch { setError("관심 상품을 변경하지 못했어요. 다시 눌러주세요."); }
    finally { submitting.current = false; setPending(false); }
  }
  return <article className="relative min-w-0 [container-type:inline-size]">
    <button type="button" onClick={onOpen} aria-label={`${product.name} 상세 보기`} className="block w-full rounded-xl text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary-600">
      <div className="relative grid aspect-square w-full place-items-center overflow-hidden rounded-[14px] bg-[#F2F6FC]">
        <span className="absolute left-3 top-3 z-10 text-xs font-semibold text-slate-500">{rank}</span>
        {rankLabel && <span className="absolute right-2 top-2 z-10 max-w-[calc(100%-40px)] rounded-md bg-white px-2 py-1 text-[10px] font-medium text-primary-700 shadow-sm">{rankLabel}</span>}
        {product.imageUrl ? <img src={product.imageUrl} alt="" loading="lazy" className="h-full w-full object-contain p-4" /> : <ProductThumbnail className="h-full w-full bg-[#F2F6FC]" shape={product.name.includes("쿠션") ? "cushion" : "bottle"} />}
      </div>
      <p className="mt-2.5 truncate text-[11px] tracking-wide text-slate-500">{product.brand}</p>
      <p className="mt-1 min-h-[39px] line-clamp-2 text-[13px] font-semibold leading-[1.5] text-slate-800">{product.name}</p>
      <p className="mt-1.5 min-h-5 text-sm font-semibold tabular-nums text-slate-800">{product.originalPrice != null ? `${product.originalPrice.toLocaleString("ko-KR")}원` : <span className="text-xs font-normal text-slate-500">가격 정보 없음</span>}</p>
      <div className="mt-2.5 flex min-h-7 items-center justify-between gap-2 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
        <span>{score != null ? personal ? "피부 적합 점수" : "검색 점수" : "적합도 정보 없음"}</span>
        {score != null && <span className="text-xs font-semibold tabular-nums text-primary-600">{Math.round(score)}점</span>}
      </div>
    </button>
    <button type="button" onClick={() => void toggleSaved()} disabled={pending} aria-label={`${product.name} 관심 상품`} aria-pressed={saved} className={`absolute right-2 top-[calc(100cqw-48px)] grid h-10 w-10 place-items-center rounded-full bg-white shadow-sm disabled:opacity-50 ${saved ? "text-primary-600" : "text-slate-500"}`}>
      <Heart aria-hidden="true" className="h-[18px] w-[18px]" fill={saved ? "currentColor" : "none"} strokeWidth={1.7} />
    </button>
    {error && <p role="alert" className="mt-2 text-[11px] leading-4 text-red-700">{error}</p>}
  </article>;
}
