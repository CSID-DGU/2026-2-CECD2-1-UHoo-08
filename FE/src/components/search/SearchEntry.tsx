import { useState } from "react";
import {
  ArrowUpRight,
  Camera,
  Droplets,
  Layers,
  Nfc,
  Search,
  Smile,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import {
  clearRecentSearches,
  getRecentSearches,
  removeRecentSearch,
} from "../../lib/localHistory";

/**
 * 검색 전 화면. 최근 검색어, 카테고리, 질문 예시 순서로 둔다.
 *
 * 인기 검색어 자리는 비워 둔다. 검색어 순위를 내려주는 API 가 아직 없어서
 * 지어낸 순위를 보여주게 된다.
 */
const CATEGORIES = [
  { label: "베이스", query: "내 피부에 맞는 베이스 메이크업 추천해줘", icon: Layers },
  { label: "선케어", query: "내 피부에 맞는 선크림 추천해줘", icon: Sun },
  { label: "립", query: "내 퍼스널컬러에 맞는 립 추천해줘", icon: Smile },
  { label: "스킨케어", query: "내 피부에 맞는 스킨케어 추천해줘", icon: Droplets },
];

const EXAMPLES = [
  { label: "제품 정보가 궁금해요", query: "롬앤 베어 워터 쿠션", icon: Search },
  { label: "원하는 조건이 있어요", query: "여름에 쓸 가벼운 매트 쿠션 추천해줘", icon: Sparkles },
  { label: "살지 고민하고 있어요", query: "롬앤 베어 워터 쿠션, 지성 피부인데 사도 될까?", icon: ArrowUpRight },
];

export function SearchEntry({
  onSearch,
  onPhoto,
  onNfc,
  nfcSupported = false,
}: {
  onSearch: (query: string) => void;
  /** 있으면 맨 위에 '사진으로 찾기' 칸을 둔다 */
  onPhoto?: () => void;
  /** 있으면 'NFC 태그 찍기' 칸을 둔다. 지원하지 않는 기기에서는 흐리게 보여준다 */
  onNfc?: () => void;
  nfcSupported?: boolean;
}) {
  const [recent, setRecent] = useState(getRecentSearches);

  return (
    <div className="mt-6">
      {(onPhoto || onNfc) && (
        <div className="mb-8 grid grid-cols-2 gap-2">
          {onPhoto && (
            <button
              type="button"
              onClick={onPhoto}
              className="flex items-center gap-2.5 rounded-2xl bg-surface-tint p-3.5 text-left"
            >
              <Camera aria-hidden="true" className="h-5 w-5 shrink-0 text-primary-800" />
              <span className="min-w-0">
                <span className="block text-caption font-semibold text-slate-800">사진으로 찾기</span>
                <span className="block truncate text-[11px] text-slate-500">찍거나 앨범에서</span>
              </span>
            </button>
          )}
          {onNfc && (
            <button
              type="button"
              onClick={onNfc}
              disabled={!nfcSupported}
              className="flex items-center gap-2.5 rounded-2xl bg-surface-tint p-3.5 text-left disabled:opacity-45"
            >
              <Nfc aria-hidden="true" className="h-5 w-5 shrink-0 text-primary-800" />
              <span className="min-w-0">
                <span className="block text-caption font-semibold text-slate-800">NFC 태그 찍기</span>
                <span className="block truncate text-[11px] text-slate-500">
                  {nfcSupported ? "매장 태그에 대기" : "안드로이드 크롬 전용"}
                </span>
              </span>
            </button>
          )}
        </div>
      )}

      {recent.length > 0 && (
        <section aria-labelledby="recent-searches-title">
          <div className="flex items-center justify-between">
            <h2 id="recent-searches-title" className="text-body1 font-semibold text-slate-800">
              최근 검색어
            </h2>
            <button
              type="button"
              onClick={() => setRecent(clearRecentSearches())}
              className="min-h-10 text-caption text-slate-500"
            >
              전체삭제
            </button>
          </div>
          <ul className="-mx-[18px] mt-2 flex gap-2 overflow-x-auto px-[18px] pb-1 scrollbar-none">
            {recent.map((query) => (
              <li
                key={query}
                className="flex shrink-0 items-center rounded-full border border-slate-200 bg-white pl-3.5 pr-1"
              >
                <button
                  type="button"
                  onClick={() => onSearch(query)}
                  className="max-w-[200px] truncate py-2 text-caption text-slate-700"
                >
                  {query}
                </button>
                <button
                  type="button"
                  aria-label={`최근 검색어 ${query} 삭제`}
                  onClick={() => setRecent(removeRecentSearch(query))}
                  className="grid h-8 w-8 place-items-center text-slate-400"
                >
                  <X aria-hidden="true" className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="search-categories-title" className={recent.length ? "mt-8" : ""}>
        <h2 id="search-categories-title" className="text-body1 font-semibold text-slate-800">
          카테고리
        </h2>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {CATEGORIES.map(({ label, query, icon: Icon }) => (
            <button
              key={label}
              type="button"
              onClick={() => onSearch(query)}
              className="flex flex-col items-center gap-2 rounded-2xl py-2"
            >
              <span className="grid h-14 w-14 place-items-center rounded-full bg-surface-tint text-primary-800">
                <Icon aria-hidden="true" className="h-6 w-6" strokeWidth={1.7} />
              </span>
              <span className="text-caption text-slate-700">{label}</span>
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="search-examples-title" className="mt-8">
        <h2 id="search-examples-title" className="text-body1 font-semibold text-slate-800">
          이렇게 물어보세요
        </h2>
        <p className="mt-1 text-caption text-slate-500">
          제품 이름도, 원하는 조건도, 살지 고민되는 것도 괜찮아요
        </p>
        <div className="mt-3 grid gap-2">
          {EXAMPLES.map(({ label, query, icon: Icon }) => (
            <button
              key={label}
              type="button"
              onClick={() => onSearch(query)}
              className="flex min-h-[68px] items-center gap-3 rounded-2xl border border-slate-100 bg-white p-3.5 text-left"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-600">
                <Icon aria-hidden="true" className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-caption leading-5 text-slate-700">{query}</span>
                <span className="mt-0.5 block text-[11px] text-slate-500">{label}</span>
              </span>
              <ArrowUpRight aria-hidden="true" className="h-4 w-4 shrink-0 text-slate-400" />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
