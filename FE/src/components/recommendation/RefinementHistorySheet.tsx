import { BottomSheet } from "../common/BottomSheet";
import type { AiSearchProduct } from "../../api/productApi";

export interface SearchHistoryEntry {
  title: string;
  conditions: string[];
  baseQuery: string;
  products: AiSearchProduct[];
}

export function RefinementHistorySheet({
  entries,
  activeIndex,
  onClose,
  onSelect,
}: {
  entries: SearchHistoryEntry[];
  activeIndex: number;
  onClose: () => void;
  onSelect: (index: number) => void;
}) {
  return (
    <BottomSheet label="조건 수정 이력" onClose={onClose}>
      <div className="px-5 pb-5 pt-3">
        <div className="flex justify-between">
          <h2 className="text-body1 font-semibold">조건 수정 이력</h2>
          <button type="button" aria-label="수정 이력 닫기" onClick={onClose}>
            ×
          </button>
        </div>
        <p className="mt-1 text-caption text-gray-300">
          원하는 시점으로 되돌릴 수 있어요
        </p>
        <ol className="mt-4 grid gap-2">
          {entries.map((entry, index) => (
            <li
              key={index}
              className={`relative rounded-xl border p-3 pl-7 ${activeIndex === index ? "border-primary-300 bg-primary-50" : "border-gray-100"}`}
            >
              <span
                className={`absolute left-3 top-4 h-2 w-2 rounded-full border ${activeIndex === index ? "border-primary-500 bg-primary-500" : "border-gray-200"}`}
              />
              <div className="flex justify-between gap-2">
                <p className="text-caption font-semibold">{entry.title}</p>
                <span className="shrink-0 text-[11px] text-gray-300">
                  후보 {entry.products.length}개
                </span>
              </div>
              <p className="mt-1 text-[11px] text-gray-300">
                {[entry.baseQuery, ...entry.conditions].join(" · ")}
              </p>
              <button
                type="button"
                onClick={() => onSelect(index)}
                disabled={index === activeIndex}
                className={`mt-2 rounded-md px-2 py-1 text-[11px] ${index === activeIndex ? "bg-primary-500 text-white" : "border border-gray-200 bg-white text-gray-400"}`}
              >
                {index === activeIndex ? "지금 보고 있어요" : "이 시점으로"}
              </button>
            </li>
          ))}
        </ol>

        <p className="mt-4 rounded-lg bg-gray-100 p-3 text-[11px] leading-5 text-gray-300">
          조건을 더하면 후보를 다시 찾아요
          <br />
          조건에 따라 후보 수와 추천 순서가 달라질 수 있어요
        </p>
      </div>
    </BottomSheet>
  );
}
