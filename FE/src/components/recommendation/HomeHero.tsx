import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  BadgeCheck,
  Sparkles,
  Sun,
  TrendingDown,
  X,
} from "lucide-react";
import { BottomSheet } from "../common/BottomSheet";
import { HeroBackdrop } from "./HeroBackdrop";

/**
 * 홈 히어로. 화담의 대표 기능 네 가지를 알린다.
 *
 * 지금 실제로 쓸 수 있는 기능만 둔다. 준비 중인 기능(소진 예측, 성분 충돌, 예산 세트)을
 * 맨 앞에서 홍보하면 눌렀을 때 실망만 남는다. 완성되면 여기에 다시 넣는다.
 */
const slides = [
  {
    id: "evaluate",
    label: "피부 적합도",
    title: "눈여겨본 그 제품,\n내 피부엔 몇 점일까?",
    description: "피부 타입과 고민, 비슷한 사람들의 후기로 0~100점을 매기고 더 나은 대안도 찾아요.",
    cta: "평가할 제품 고르기",
    icon: BadgeCheck,
  },
  {
    id: "search",
    label: "AI 맞춤 검색",
    title: "원하는 걸 말하면,\nAI가 골라드려요",
    description: "가격, 제형, 피부 고민까지 한 문장으로 알려주세요.",
    cta: "말로 찾아보기",
    icon: Sparkles,
  },
  {
    id: "environment",
    label: "생활 환경 케어",
    title: "요즘 햇빛과 미세먼지,\n루틴에도 반영해요",
    description: "내 지역 날씨와 화장대 센서로 지금 필요한 제품을 알려드려요.",
    cta: "내 환경 보기",
    icon: Sun,
  },
  {
    id: "price",
    label: "최저가 추적",
    title: "사고 싶은 그 제품,\n가장 쌀 때 알려드려요",
    description: "여러 쇼핑몰 가격을 비교하고, 목표가에 닿으면 알림을 보내드려요.",
    cta: "가격 추적 시작하기",
    icon: TrendingDown,
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
  const [sheet, setSheet] = useState<"search" | null>(null);
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
  function open(id: string) {
    if (id === "search") {
      setQuery("");
      setSheet("search");
    } else if (id === "evaluate") onEvaluate();
    else if (id === "environment") navigate("/environment");
    else if (id === "price") navigate("/favorites");
  }
  return (
    <>
      <section
        aria-label="화담 대표 기능"
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
        className="group relative isolate -mx-5 overflow-hidden"
        style={{ touchAction: "pan-y" }}
      >
        <HeroBackdrop />
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
              >
                <div className="relative z-10 max-w-[270px]">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1 rounded-full bg-white/85 px-2.5 py-1 text-[10px] font-semibold text-[#2C507D]">
                      <Icon aria-hidden="true" className="h-3 w-3" strokeWidth={2} />
                      {slide.label}
                    </span>
                  </div>
                  <h2 className="mt-4 whitespace-pre-line text-[23px] font-bold leading-[1.4] tracking-tight text-[#203D66]">
                    {slide.title}
                  </h2>
                  <p className="mt-3 min-h-10 max-w-[238px] text-[12px] leading-5 text-[#304B70]">
                    {slide.description}
                  </p>
                  <button
                    type="button"
                    onClick={() => open(slide.id)}
                    className="mt-4 flex min-h-10 items-center gap-2 rounded-full border border-white bg-white px-4 py-2.5 text-[11px] font-semibold text-[#203D66] shadow-[0_3px_10px_rgba(32,61,102,0.08)]"
                  >
                    {slide.cta}
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        <div aria-hidden="true" className="absolute bottom-4 left-9 z-20 flex gap-1.5">
          {slides.map((slide, index) => {
            const current = ((position - 1 + slides.length) % slides.length) === index;
            return (
              <span
                key={slide.id}
                className={`h-1.5 rounded-full transition-all ${current ? "w-5 bg-[#203D66]" : "w-1.5 bg-[#203D66]/30"}`}
              />
            );
          })}
        </div>
        <button
          type="button"
          aria-label="이전 기능"
          onClick={() => move(-1)}
          className="pointer-events-none absolute left-1 top-1/2 z-20 grid h-9 w-8 -translate-y-1/2 place-items-center rounded-full border border-white bg-white text-[#203D66] opacity-0 shadow-md transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          type="button"
          aria-label="다음 기능"
          onClick={() => move(1)}
          className="pointer-events-none absolute right-1 top-1/2 z-20 grid h-9 w-8 -translate-y-1/2 place-items-center rounded-full border border-white bg-white text-[#203D66] opacity-0 shadow-md transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </section>
      {sheet && (
        <BottomSheet
          label="추천 조건 입력"
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
                어떤 제품을 찾으세요?
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
              가격, 제형, 피부 고민을 편하게 적어주세요.
            </p>
            <label
              className="mt-4 block text-xs font-medium"
              htmlFor="hero-query"
            >
              원하는 조건
            </label>
            <input
              id="hero-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="예) 여름에 쓸 가벼운 매트 쿠션"
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
