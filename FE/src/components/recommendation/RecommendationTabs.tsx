export type RecommendationBasis = "SELF" | "POPULAR" | "OTHER";

interface RecommendationTabsProps {
  value: RecommendationBasis;
  onChange: (value: RecommendationBasis) => void;
  enabledBases?: readonly RecommendationBasis[];
}

const TABS: {
  value: RecommendationBasis;
  label: string;
}[] = [
  { value: "SELF", label: "내 피부 기준" },
  { value: "POPULAR", label: "전체 인기" },
  { value: "OTHER", label: "다른 사람" },
];

const DEFAULT_ENABLED: readonly RecommendationBasis[] = ["SELF"];

export function RecommendationTabs({
  value,
  onChange,
  enabledBases = DEFAULT_ENABLED,
}: RecommendationTabsProps) {
  return (
    <div
      role="group"
      aria-label="추천 기준"
      className="grid grid-cols-3 gap-1 rounded-xl bg-gray-100 p-1"
    >
      {TABS.map((tab) => {
        const selected = value === tab.value;
        const enabled = enabledBases.includes(tab.value);

        return (
          <button
            key={tab.value}
            type="button"
            disabled={!enabled}
            aria-pressed={selected}
            title={enabled ? undefined : "준비 중"}
            onClick={() => onChange(tab.value)}
            className={[
              "min-h-10 rounded-lg px-2 text-caption font-semibold",
              "transition-colors",
              "focus-visible:outline-2",
              "focus-visible:outline-offset-2",
              "focus-visible:outline-primary-500",
              "disabled:cursor-not-allowed",
              selected
                ? "bg-primary-500 text-white shadow-sm"
                : "text-gray-300",
            ].join(" ")}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
