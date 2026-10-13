import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Check,
  FlaskConical,
  Layers,
  Leaf,
  SlidersHorizontal,
  Sun,
  Wallet,
  X,
} from "lucide-react";
import { BottomSheet } from "../common/BottomSheet";

const slides = [
  {
    id: "S1",
    label: "상품 평가 · 대체",
    title: "눈여겨본 그 제품,\n내 피부에도 잘 맞을까?",
    description: "기준 제품을 골라 분석 이유와 대체 후보를 확인해요.",
    cta: "평가할 제품 찾기",
    icon: Check,
    accent: "#9DBDE9",
    tint: "#9DBDE9",
    kind: "evaluate",
  },
  {
    id: "S2",
    label: "조건 탐색",
    title: "원하는 조건을 말하면,\n후보가 좁혀져요",
    description: "가격, 제형, 피부 고민까지 한 문장으로 알려주세요.",
    cta: "내 조건 입력하기",
    icon: SlidersHorizontal,
    accent: "#9DBDE9",
    tint: "#A8C6EC",
    kind: "search",
  },
  {
    id: "S3",
    label: "생활 환경 기반 추천",
    title: "오늘의 햇빛과 습도,\n루틴에도 반영해요",
    description: "생활 공간의 측정 환경과 함께 제품을 살펴봐요.",
    cta: "내 환경 살펴보기",
    icon: Sun,
    accent: "#9DBDE9",
    tint: "#AED0DB",
    kind: "environment",
  },
  {
    id: "S4",
    label: "소진 예측 · 재구매 / 대체",
    title: "다 쓰기 전에,\n다음 제품도 생각해요",
    description:
      "쓰는 제품부터 모아두세요. 소진 예측과 재구매 안내를 준비하고 있어요.",
    cta: "쓰는 제품 관리하기",
    icon: Leaf,
    accent: "#9DBDE9",
    tint: "#AED0DB",
    kind: "inventory",
    upcoming: true,
  },
  {
    id: "S5",
    label: "성분 충돌 검사",
    title: "함께 쓰는 두 제품,\n궁합도 중요하니까",
    description:
      "제품 성분부터 살펴보세요. 제품 간 충돌 검사를 준비하고 있어요.",
    cta: "제품 정보 찾아보기",
    icon: FlaskConical,
    accent: "#9DBDE9",
    tint: "#B8BFE7",
    kind: "ingredients",
    upcoming: true,
  },
  {
    id: "S6",
    label: "예산 세트 구성",
    title: "정해둔 예산 안에서,\n필요한 구성까지",
    description:
      "예산과 구성을 알려주세요. 세트 구성은 준비 중이며 지금은 조건 검색으로 연결돼요.",
    cta: "예산과 구성 입력하기",
    icon: Wallet,
    accent: "#9DBDE9",
    tint: "#D6C6BC",
    kind: "budget",
    upcoming: true,
  },
  {
    id: "S7",
    label: "조건 수정 · 재탐색",
    title: "조금 더 저렴하게?\n조건을 더해 좁혀요",
    description: "검색 결과에서 조건을 더하거나 바꾸고, 이전 결과와 비교해요.",
    cta: "조건 수정하러 가기",
    icon: Layers,
    accent: "#9DBDE9",
    tint: "#A8C6EC",
    kind: "refine",
  },
];
const track = [slides[slides.length - 1], ...slides, slides[0]];

export function HomeHero({
  onSearch,
  onEvaluate,
}: {
  onSearch: (query: string) => void;
  onEvaluate: () => void;
}) {
  const navigate = useNavigate();
  const [position, setPosition] = useState(1);
  const [animate, setAnimate] = useState(true);

  const [interacting, setInteracting] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [hidden, setHidden] = useState(document.hidden);
  const [sheet, setSheet] = useState<"search" | "budget" | null>(null);
  const [query, setQuery] = useState("");
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const moving = useRef(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    const visibility = () => setHidden(document.hidden);
    media.addEventListener("change", update);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      media.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  useEffect(() => {
    if (!moving.current) return;
    const timer = window.setTimeout(
      () => {
        if (position === 0 || position === slides.length + 1) {
          setAnimate(false);
          setPosition(position === 0 ? slides.length : 1);
        }
        moving.current = false;
      },
      reducedMotion ? 0 : 620,
    );
    return () => window.clearTimeout(timer);
  }, [position, reducedMotion]);
  useEffect(() => {
    if (animate) return;
    const timer = window.setTimeout(() => setAnimate(true), 30);
    return () => window.clearTimeout(timer);
  }, [animate]);
  useEffect(() => {
    if (interacting || reducedMotion || hidden || sheet) return;
    const timer = window.setTimeout(() => {
      moving.current = true;
      setPosition((index) => index + 1);
    }, 5500);
    return () => window.clearTimeout(timer);
  }, [position, interacting, reducedMotion, hidden, sheet]);
  const move = (direction: number) => {
    if (moving.current) return;
    moving.current = true;
    setPosition((index) => index + direction);
  };
  function open(kind: string) {
    if (kind === "search" || kind === "budget") {
      setQuery("");
      setSheet(kind);
    } else if (kind === "evaluate") onEvaluate();
    else if (kind === "environment") navigate("/environment");
    else if (kind === "inventory") navigate("/my/products");
    else if (kind === "ingredients") navigate("/recommendation/lookup");
    else navigate("/search", { state: { entryScenario: "refine" } });
  }
  return (
    <>
      <section
        aria-label="화담 추천 시나리오"
        aria-roledescription="캐러셀"
        onMouseEnter={() => setInteracting(true)}
        onMouseLeave={() => setInteracting(false)}
        onFocusCapture={() => setInteracting(true)}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget))
            setInteracting(false);
        }}
        onKeyDown={(event) => {
          if (event.target instanceof HTMLInputElement) return;
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            move(event.key === "ArrowLeft" ? -1 : 1);
          }
        }}
        onTouchStart={(event) => {
          touchStart.current = {
            x: event.touches[0].clientX,
            y: event.touches[0].clientY,
          };
          setInteracting(true);
        }}
        onTouchCancel={() => {
          touchStart.current = null;
          setInteracting(false);
        }}
        onTouchEnd={(event) => {
          const start = touchStart.current;
          if (start) {
            const dx = event.changedTouches[0].clientX - start.x;
            const dy = event.changedTouches[0].clientY - start.y;
            if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy))
              move(dx < 0 ? 1 : -1);
          }
          touchStart.current = null;
          setInteracting(false);
        }}
        className="group relative isolate -mx-5 overflow-hidden bg-[#9DBDE9]"
        style={{ touchAction: "pan-y" }}
      >
        <div
          className="flex"
          style={{
            transform: `translateX(-${position * 100}%)`,
            transition:
              animate && !reducedMotion
                ? "transform 600ms cubic-bezier(.22,1,.36,1)"
                : "none",
          }}
        >
          {track.map((slide, index) => {
            const Icon = slide.icon;
            const visible = position === index;
            return (
              <div
                key={`${slide.id}-${index}`}
                role="group"
                aria-roledescription="슬라이드"
                aria-label={`${slide.id}: ${slide.label}`}
                aria-hidden={!visible}
                inert={!visible}
                className="relative min-h-[300px] w-full shrink-0 overflow-hidden px-9 py-6"
                style={{
                  background: `linear-gradient(135deg, ${slide.tint} 0%, #C5D8F0 100%)`,
                }}
              >
                <div className="relative z-10 max-w-[270px]">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-semibold text-[#2C507D]">
                      {slide.label}
                    </span>
                    {slide.upcoming && (
                      <span className="text-[10px] text-[#405979]">
                        준비 중
                      </span>
                    )}
                  </div>
                  <h2 className="mt-4 whitespace-pre-line text-[23px] font-bold leading-[1.4] tracking-tight text-[#203D66]">
                    {slide.title}
                  </h2>
                  <p className="mt-3 min-h-10 max-w-[238px] text-[12px] leading-5 text-[#304B70]">
                    {slide.description}
                  </p>
                  <button
                    type="button"
                    onClick={() => open(slide.kind)}
                    className="mt-4 flex min-h-10 items-center gap-2 rounded-full border border-white bg-white px-4 py-2.5 text-[11px] font-semibold text-[#203D66] shadow-[0_3px_10px_rgba(32,61,102,0.08)]"
                  >
                    {slide.cta}
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-6 -right-7 h-40 w-40 rounded-full border-[18px] border-white/35"
                >
                  <div
                    className="absolute inset-5 grid place-items-center rounded-[28px] border border-white/70 bg-white/35"
                    style={{ transform: "rotate(-12deg)" }}
                  >
                    <Icon
                      className="h-10 w-10 text-[#527CB6]"
                      style={{ transform: "rotate(12deg)" }}
                      strokeWidth={1.5}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <button
          type="button"
          aria-label="이전 시나리오"
          onClick={() => move(-1)}
          className="pointer-events-none absolute left-1 top-1/2 z-20 grid h-9 w-8 -translate-y-1/2 place-items-center rounded-full border border-white bg-white text-[#203D66] opacity-0 shadow-md transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          type="button"
          aria-label="다음 시나리오"
          onClick={() => move(1)}
          className="pointer-events-none absolute right-1 top-1/2 z-20 grid h-9 w-8 -translate-y-1/2 place-items-center rounded-full border border-white bg-white text-[#203D66] opacity-0 shadow-md transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </section>
      {sheet && (
        <BottomSheet
          label={sheet === "budget" ? "예산과 구성 입력" : "추천 조건 입력"}
          onClose={() => setSheet(null)}
        >
          <form
            className="px-5 pb-6 pt-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!query.trim()) return;
              setSheet(null);
              onSearch(query.trim());
            }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                {sheet === "budget"
                  ? "예산과 구성을 알려주세요"
                  : "어떤 제품을 찾으세요?"}
              </h2>
              <button
                type="button"
                aria-label="닫기"
                className="grid h-10 w-10 place-items-center"
                onClick={() => setSheet(null)}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-1 text-xs leading-5 text-gray-300">
              {sheet === "budget"
                ? "세트 구성은 준비 중이에요. 지금은 입력한 조건으로 제품을 찾아드려요."
                : "가격, 제형, 피부 고민을 편하게 적어주세요."}
            </p>
            <label
              className="mt-4 block text-xs font-medium"
              htmlFor="hero-query"
            >
              {sheet === "budget" ? "예산과 필요한 제품" : "원하는 조건"}
            </label>
            <input
              id="hero-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={
                sheet === "budget"
                  ? "예) 5만원 안에서 스킨과 로션"
                  : "예) 여름에 쓸 가벼운 매트 쿠션"
              }
              className="mt-2 h-12 w-full rounded-xl border border-[#9DBDE9] px-3 text-sm outline-none focus:ring-2 focus:ring-[#9DBDE9]/40"
            />
            <button
              type="submit"
              disabled={!query.trim()}
              className="mt-4 min-h-12 w-full rounded-xl bg-[#9DBDE9] text-sm font-semibold text-[#203D66] disabled:opacity-40"
            >
              이 조건으로 검색하기
            </button>
          </form>
        </BottomSheet>
      )}
    </>
  );
}
