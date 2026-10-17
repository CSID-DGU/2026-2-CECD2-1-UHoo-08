import { ArrowUpRight, Search, Sparkles } from "lucide-react";

const EXAMPLES = [
  { label: "제품 정보가 궁금해요", query: "롬앤 베어 워터 쿠션", icon: Search },
  {
    label: "원하는 조건이 있어요",
    query: "여름에 쓸 가벼운 매트 쿠션 추천해줘",
    icon: Sparkles,
  },
  {
    label: "살지 고민하고 있어요",
    query: "롬앤 베어 워터 쿠션, 지성 피부인데 사도 될까?",
    icon: ArrowUpRight,
  },
];

export function SearchEntry({
  onSearch,
}: {
  onSearch: (query: string) => void;
}) {
  return (
    <div className="mt-8">
      <h1 className="text-h2 text-gray-500">
        찾고 싶은 제품도,
        <br />
        궁금한 점도 말해보세요
      </h1>
      <p className="mt-3 text-body2 leading-6 text-gray-300">
        제품을 찾아보거나 원하는 조건을 알려주세요.
        <br />
        살지 고민되는 제품도 함께 살펴볼 수 있어요.
      </p>
      <div className="mt-7 grid gap-3">
        {EXAMPLES.map(({ label, query, icon: Icon }) => (
          <button
            key={label}
            type="button"
            onClick={() => onSearch(query)}
            className="flex min-h-20 items-center gap-3 rounded-2xl border border-gray-100 bg-white p-4 text-left"
          >
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-600">
              <Icon className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-caption text-gray-300">{label}</span>
              <span className="mt-1 block text-body2 leading-5 text-gray-500">
                {query}
              </span>
            </span>
            <ArrowUpRight
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-gray-300"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
