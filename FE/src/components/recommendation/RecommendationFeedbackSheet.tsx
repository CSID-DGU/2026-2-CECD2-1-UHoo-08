import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { AiSearchProduct } from "../../api/productApi";
import { ProductThumbnail } from "../common/ProductThumbnail";
import { PrimaryButton } from "../common/PrimaryButton";
import { BottomSheet } from "../common/BottomSheet";

export type FeedbackValue = { liked: boolean; reasons: string[] };
const REASONS = [
  "너무 비싸요",
  "내 피부에 안 맞을 것 같아요",
  "후기가 별로예요",
  "이미 비슷한 걸 써요",
];

export function RecommendationFeedbackSheet({
  product,
  initialLiked,
  onClose,
  onSubmit,
}: {
  product: AiSearchProduct;
  initialLiked: boolean;
  onClose: () => void;
  onSubmit: (value: FeedbackValue) => void;
}) {
  const [liked, setLiked] = useState(initialLiked);
  const [reasons, setReasons] = useState<string[]>([]);

  return (
    <BottomSheet label="추천 피드백" onClose={onClose}>
      <div className="px-5 pb-5 pt-3">
        <div className="flex items-center justify-between">
          <h2 id="feedback-title" className="text-body1 font-semibold">
            이 추천, 어땠나요?
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="피드백 닫기"
            className="px-2 text-gray-300"
          >
            ×
          </button>
        </div>
        <p className="mt-1 text-caption text-gray-300">
          알려주시면 다음 추천부터 반영해요
        </p>
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-gray-100 p-3">
          <ProductThumbnail
            className="h-12 w-12 shrink-0 bg-primary-50"
            size="sm"
            green
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-caption font-semibold">
              {product.name}
            </p>
            <p className="mt-1 text-[11px] text-gray-300">
              {product.brand} · {product.originalPrice?.toLocaleString("ko-KR")}
              원
            </p>
          </div>
          <span className="rounded-md bg-primary-50 px-2 py-1 text-[11px] text-primary-500">
            {product.matchScore}%
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[true, false].map((value) => {
            const Icon = value ? ThumbsUp : ThumbsDown;
            return (
              <button
                key={String(value)}
                type="button"
                aria-pressed={liked === value}
                onClick={() => {
                  setLiked(value);
                  setReasons([]);
                }}
                className={`flex items-center justify-center gap-2 rounded-xl border py-3 text-caption ${liked === value ? "border-primary-300 bg-primary-50 text-primary-500" : "border-gray-100 text-gray-300"}`}
              >
                <Icon className="h-4 w-4" />
                {value ? "좋아요" : "별로예요"}
              </button>
            );
          })}
        </div>
        {!liked && (
          <fieldset className="mt-4">
            <legend className="mb-2 text-caption font-semibold">
              어떤 점이 아쉬웠나요?{" "}
              <span className="font-normal text-gray-300">복수 선택돼요</span>
            </legend>
            <div className="flex flex-wrap gap-2">
              {REASONS.map((reason) => (
                <button
                  type="button"
                  key={reason}
                  aria-pressed={reasons.includes(reason)}
                  onClick={() =>
                    setReasons((previous) =>
                      previous.includes(reason)
                        ? previous.filter((item) => item !== reason)
                        : [...previous, reason],
                    )
                  }
                  className={`rounded-lg px-3 py-2 text-[11px] ${reasons.includes(reason) ? "bg-primary-300 text-white" : "bg-gray-100 text-gray-400"}`}
                >
                  {reason}
                </button>
              ))}
            </div>
          </fieldset>
        )}
        <div className="mt-4 rounded-xl border border-primary-100 bg-primary-50 p-3">
          <p className="text-caption font-semibold text-primary-500">
            이렇게 반영돼요
          </p>
          <p className="mt-1 text-[11px] leading-5 text-gray-400">
            {reasons.includes("너무 비싸요")
              ? "‘너무 비싸요’ → 다음 추천부터 가격을 조금 더 중요하게 봐요."
              : liked
                ? "마음에 드는 추천의 특징을 다음 추천에 참고해요."
                : "선택한 이유를 다음 추천 조건에 참고해요."}
            <br />한 번에 조금씩만 바뀌고, 마이페이지에서 되돌릴 수 있어요.
          </p>
        </div>
        <PrimaryButton
          className="mt-4"
          onClick={() => onSubmit({ liked, reasons })}
        >
          보내기
        </PrimaryButton>
      </div>
    </BottomSheet>
  );
}
