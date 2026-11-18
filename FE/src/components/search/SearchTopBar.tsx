import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Camera, Search, X } from "lucide-react";
import { searchProducts, type ProductSearchItem } from "../../api/productApi";

const PREVIEW_MIN_LENGTH = 2;
const PREVIEW_DELAY_MS = 250;
const PREVIEW_LIMIT = 5;

/**
 * 검색 화면 맨 위 한 줄. 뒤로가기, 입력창, 검색 버튼을 한 줄에 둔다.
 *
 * 입력하는 동안 제품명이 맞는 제품을 아래에 미리 보여준다. 누르면 바로 상세로 간다.
 * 엔터나 검색 버튼은 전체 검색이다.
 *
 * value 가 바뀌면(최근 검색어를 누르거나 결과를 복원했을 때) 입력창도 그 값으로 맞춘다.
 */
export function SearchTopBar({
  value,
  autoFocus = false,
  placeholder = "제품명이나 궁금한 점을 입력하세요",
  onBack,
  onSubmit,
  onSelectProduct,
  onLens,
}: {
  value: string;
  autoFocus?: boolean;
  placeholder?: string;
  onBack: () => void;
  onSubmit: (query: string) => void;
  /** 있으면 입력 중 미리보기를 켠다 */
  onSelectProduct?: (product: ProductSearchItem) => void;
  /** 있으면 입력창 안에 카메라 버튼을 둔다(사진·NFC로 찾기) */
  onLens?: () => void;
}) {
  const [text, setText] = useState(value);
  const [focused, setFocused] = useState(false);
  // 어떤 검색어에 대한 결과인지 같이 둔다. 늦게 온 이전 응답을 걸러내기 위해서다.
  const [preview, setPreview] = useState<{ query: string; items: ProductSearchItem[] }>({
    query: "",
    items: [],
  });
  const input = useRef<HTMLInputElement>(null);

  // 바깥 값이 바뀐 렌더에서 바로 맞춘다(effect 로 맞추면 한 번 더 그린다).
  const [synced, setSynced] = useState(value);
  if (synced !== value) {
    setSynced(value);
    setText(value);
  }
  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);

  const query = text.trim();
  const wantsPreview =
    Boolean(onSelectProduct) && focused && query.length >= PREVIEW_MIN_LENGTH && query !== value;

  useEffect(() => {
    if (!wantsPreview) return;
    let active = true;
    const timer = window.setTimeout(() => {
      searchProducts(query)
        .then(({ data }) => {
          if (!active) return;
          const items = Array.isArray(data?.products) ? data.products.slice(0, PREVIEW_LIMIT) : [];
          setPreview({ query, items });
        })
        .catch(() => {
          if (active) setPreview({ query, items: [] });
        });
    }, PREVIEW_DELAY_MS);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [wantsPreview, query]);

  const items = wantsPreview && preview.query === query ? preview.items : [];

  function submit() {
    if (!query) return;
    input.current?.blur(); // 키보드를 내려 결과가 보이게 한다.
    onSubmit(query);
  }

  return (
    <header
      className="relative flex items-center gap-2"
      // 포커스가 입력창에서 미리보기 항목(키보드 Tab 이동 포함)으로 옮겨가도 목록을 닫지 않는다.
      // 검색 바 전체 밖으로 나갈 때만 닫는다.
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
      }}
    >
      <button
        type="button"
        onClick={onBack}
        aria-label="뒤로가기"
        className="grid h-10 w-9 shrink-0 place-items-center text-slate-700"
      >
        <ArrowLeft aria-hidden="true" className="h-6 w-6" strokeWidth={1.8} />
      </button>
      <form
        role="search"
        className="flex h-12 min-w-0 flex-1 items-center gap-2 rounded-full border border-slate-200 bg-white pl-4 pr-1.5 shadow-[0_2px_10px_rgba(32,61,102,0.06)] focus-within:border-primary-300"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <input
          ref={input}
          type="search"
          enterKeyHint="search"
          autoComplete="off"
          aria-label="화장품 검색"
          aria-autocomplete="list"
          aria-controls="search-preview"
          aria-expanded={items.length > 0}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-body2 text-slate-800 outline-none placeholder:text-slate-400 [&::-webkit-search-cancel-button]:hidden"
        />
        {text && (
          <button
            type="button"
            aria-label="검색어 지우기"
            onClick={() => {
              setText("");
              input.current?.focus();
            }}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-slate-400"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        )}
        {onLens && !text && (
          <button
            type="button"
            aria-label="사진이나 NFC로 제품 찾기"
            onClick={onLens}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-slate-500"
          >
            <Camera aria-hidden="true" className="h-5 w-5" strokeWidth={1.8} />
          </button>
        )}
        <button
          type="submit"
          aria-label="검색하기"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-slate-700"
        >
          <Search aria-hidden="true" className="h-5 w-5" strokeWidth={2} />
        </button>
      </form>

      {items.length > 0 && (
        <ul
          id="search-preview"
          aria-label="제품 미리보기"
          className="absolute left-11 right-0 top-[calc(100%+6px)] z-40 overflow-hidden rounded-2xl border border-slate-100 bg-white py-1 shadow-[0_8px_24px_rgba(32,61,102,0.14)]"
        >
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setFocused(false);
                  onSelectProduct?.(item);
                }}
                className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-[#F2F6FC]"
              >
                {item.imageUrl ? (
                  <img
                    src={item.imageUrl}
                    alt=""
                    className="h-10 w-10 shrink-0 rounded-lg bg-[#F2F6FC] object-contain p-0.5"
                  />
                ) : (
                  <span className="h-10 w-10 shrink-0 rounded-lg bg-[#F2F6FC]" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] text-slate-500">{item.brand}</span>
                  <span className="block truncate text-caption text-slate-800">{item.name}</span>
                </span>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={submit}
              className="flex w-full items-center gap-2 border-t border-slate-100 px-3 py-2.5 text-left text-caption text-primary-600"
            >
              <Search aria-hidden="true" className="h-4 w-4" /> ‘{query}’ 전체 검색
            </button>
          </li>
        </ul>
      )}
    </header>
  );
}
