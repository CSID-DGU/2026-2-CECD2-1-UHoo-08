import { useRef, useState } from "react";
import { Heart, Star, ThumbsUp } from "lucide-react";
import type { AiSearchProduct } from "../../api/productApi";
import { ProductThumbnail } from "../common/ProductThumbnail";

export function SearchProductCard({ product, rank, rankLabel, personalization, rating, reviewCount, showScore = true, reason, feedbackSent, saved, onOpen, onToggleSaved, onFeedback }: {
  product: AiSearchProduct;
  rank: number;
  rankLabel: string | null;
  personalization?: number | null;
  /** 인기 기준 결과의 평점과 리뷰 수. 점수 대신 보여준다 */
  rating?: number | null;
  reviewCount?: number | null;
  /** 점수 줄을 보여줄지. 제품명 검색 결과처럼 점수가 없는 목록은 숨긴다 */
  showScore?: boolean;
  /** 추천 이유 한 줄 */
  reason?: string | null;
  /** 이미 피드백을 보낸 제품 */
  feedbackSent?: boolean;
  saved: boolean;
  onOpen: () => void;
  onToggleSaved: () => Promise<void>;
  /** 있으면 '이 추천 어땠나요' 버튼을 보여준다 */
  onFeedback?: () => void;
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
      <div className="relative grid aspect-square w-full place-items-center overflow-hidden rounded-[14px] bg-surface-tint">
        <span className="absolute left-3 top-3 z-10 text-xs font-semibold text-slate-500">{rank}</span>
        {rankLabel && <span className="absolute right-2 top-2 z-10 max-w-[calc(100%-40px)] rounded-md bg-white px-2 py-1 text-[11px] font-medium text-primary-700 shadow-sm">{rankLabel}</span>}
        {product.imageUrl ? <img src={product.imageUrl} alt="" loading={rank <= 2 ? "eager" : "lazy"} className="h-full w-full object-contain p-4" /> : <ProductThumbnail className="h-full w-full bg-surface-tint" shape={product.name.includes("쿠션") ? "cushion" : "bottle"} />}
      </div>
      <p className="mt-2.5 truncate text-[11px] tracking-wide text-slate-500">{product.brand}</p>
      <p className="mt-1 min-h-[39px] line-clamp-2 text-[13px] font-semibold leading-[1.5] text-slate-800">{product.name}</p>
      <p className="mt-1.5 min-h-5 text-sm font-semibold tabular-nums text-slate-800">{product.originalPrice != null ? `${product.originalPrice.toLocaleString("ko-KR")}원` : <span className="text-xs font-normal text-slate-500">가격 정보 없음</span>}</p>
      {showScore && <div className="mt-2.5 flex min-h-7 items-center justify-between gap-2 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
        {score == null && rating != null ? <>
          <span className="flex gap-2"><span>평점</span>{reviewCount != null && <span>리뷰 {reviewCount.toLocaleString("ko-KR")}</span>}</span>
          <span className="text-xs font-semibold tabular-nums text-primary-600"><Star aria-hidden="true" className="mr-0.5 inline h-3 w-3 -translate-y-px fill-current" />{rating.toFixed(1)}</span>
        </> : <>
          <span>{score != null ? personal ? "피부 적합 점수" : "검색 점수" : "적합도 정보 없음"}</span>
          {score != null && <span className="text-xs font-semibold tabular-nums text-primary-600">{Math.round(score)}점</span>}
        </>}
      </div>}
      {reason && <p className="mt-1.5 line-clamp-2 text-[11px] leading-4 text-slate-500">{reason}</p>}
    </button>
    {onFeedback && <button type="button" onClick={onFeedback} className="mt-1.5 flex min-h-8 items-center gap-1 text-[11px] text-slate-500">
      <ThumbsUp aria-hidden="true" className="h-3.5 w-3.5" /> {feedbackSent ? "피드백 다시 보내기" : "이 추천 어땠나요?"}
    </button>}
    <button type="button" onClick={() => void toggleSaved()} disabled={pending} aria-label={`${product.name} 관심 상품`} aria-pressed={saved} className={`absolute right-2 top-[calc(100cqw-48px)] grid h-10 w-10 place-items-center rounded-full bg-white shadow-sm disabled:opacity-50 ${saved ? "text-primary-600" : "text-slate-500"}`}>
      <Heart aria-hidden="true" className="h-[18px] w-[18px]" fill={saved ? "currentColor" : "none"} strokeWidth={1.7} />
    </button>
    {error && <p role="alert" className="mt-2 text-[11px] leading-4 text-red-700">{error}</p>}
  </article>;
}
