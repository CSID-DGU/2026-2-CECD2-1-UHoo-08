import { BottomSheet } from "../common/BottomSheet";

/** 조건 수정 이력 한 단계. 서버의 refinements/history 한 줄과 같다. */
export interface RefinementHistoryEntry {
  jobId: string;
  /** "처음 검색" 또는 "+ 더 저렴하게" */
  title: string;
  /** 처음 검색이면 검색 문장, 나머지는 직전 단계와 달라진 조건 */
  detail: string;
  candidateCount: number;
}

export function RefinementHistorySheet({
  entries,
  activeJobId,
  loading,
  error,
  onClose,
  onSelect,
}: {
  entries: RefinementHistoryEntry[];
  activeJobId: string | null;
  loading?: boolean;
  error?: string;
  onClose: () => void;
  onSelect: (jobId: string) => void;
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
        {loading && (
          <p role="status" className="mt-4 text-caption text-gray-300">
            이력을 불러오고 있어요
          </p>
        )}
        {!loading && error && (
          <p role="alert" className="mt-4 text-caption text-red-700">
            {error}
          </p>
        )}
        <ol className="mt-4 grid gap-2">
          {entries.map((entry) => {
            const active = entry.jobId === activeJobId;
            return (
              <li
                key={entry.jobId}
                className={`relative rounded-xl border p-3 pl-7 ${active ? "border-primary-300 bg-primary-50" : "border-gray-100"}`}
              >
                <span
                  className={`absolute left-3 top-4 h-2 w-2 rounded-full border ${active ? "border-primary-500 bg-primary-500" : "border-gray-200"}`}
                />
                <div className="flex justify-between gap-2">
                  <p className="text-caption font-semibold">{entry.title}</p>
                  <span className="shrink-0 text-[11px] text-gray-300">
                    후보 {entry.candidateCount}개
                  </span>
                </div>
                {entry.detail && (
                  <p className="mt-1 text-[11px] text-gray-300">{entry.detail}</p>
                )}
                <button
                  type="button"
                  onClick={() => onSelect(entry.jobId)}
                  disabled={active}
                  className={`mt-2 rounded-md px-2 py-1 text-[11px] ${active ? "bg-primary-600 text-white" : "border border-gray-200 bg-white text-gray-400"}`}
                >
                  {active ? "지금 보고 있어요" : "이 시점으로"}
                </button>
              </li>
            );
          })}
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
