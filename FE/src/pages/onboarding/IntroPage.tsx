import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import intro1 from "../../assets/intro/intro-1.webp";
import intro2 from "../../assets/intro/intro-2.webp";
import intro3 from "../../assets/intro/intro-3.webp";
import intro4 from "../../assets/intro/intro-4.webp";
import AppLayout from "../../layouts/AppLayout";

/**
 * 고민 → 해결 → 생활 → 시작 순서로 이야기를 잇는다. 장마다 그림 한 장과 문장 한두 줄만 둔다.
 * 그림은 720px webp 로 줄여 둔 것이다(원본 PNG 는 장당 1MB 가 넘어 저장소에 두지 않는다).
 */
const SLIDES = [
  {
    image: intro1,
    alt: "화장품 선반 앞에서 병을 들고 고민하는 사람",
    title: "수많은 화장품 중에\n내 피부에 맞는 건 뭘까요?",
  },
  {
    image: intro2,
    alt: "휴대폰 너머로 비슷한 사람들의 얼굴이 이어진 모습",
    title: "나와 피부가 닮은 사람들이\n실제로 고른 제품을 보여드려요",
  },
  {
    image: intro3,
    alt: "화장대 앞에 앉은 사람 위로 해와 미세먼지 구름이 있는 모습",
    title: "요즘 날씨와 화장대 환경까지\n함께 챙겨드려요",
  },
  {
    image: intro4,
    alt: "휴대폰 화면의 선택지를 누르는 사람",
    title: "피부 타입을 알려주시면\n추천이 더 정확해져요",
  },
];

/**
 * 서비스 소개. 처음 가입한 사용자에게 로그인 직후 한 번 보여준다.
 *
 * 목적은 홍보보다 온보딩을 끝까지 하게 하는 것이다. 피부 정보가 없으면 내 피부 기준 추천이
 * 동작하지 않는데, 왜 묻는지 모르면 대충 넣거나 건너뛴다. 그래서 마지막 장에서 그 이유를
 * 밝히고 바로 프로필 입력으로 잇는다.
 *
 * ?again=1 이면 마이페이지에서 다시 보는 것이라, 끝나면 온보딩 대신 원래 화면으로 돌아간다.
 */
export function IntroPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const again = params.get("again") === "1";
  const [step, setStep] = useState(0);
  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const last = step === SLIDES.length - 1;
  const slide = SLIDES[step];

  const finish = () => {
    if (again) navigate(-1);
    else navigate("/onboarding/profile", { replace: true });
  };
  const go = (next: number) => setStep(Math.max(0, Math.min(SLIDES.length - 1, next)));

  return (
    <AppLayout>
      <section
        className="flex min-h-screen flex-col bg-white px-6 pb-8 pt-14"
        aria-roledescription="서비스 소개"
        aria-label={`화담 소개 ${step + 1} / ${SLIDES.length}`}
        style={{ touchAction: "pan-y" }}
        onTouchStart={(event) => {
          touchStart.current = { x: event.touches[0].clientX, y: event.touches[0].clientY };
        }}
        onTouchEnd={(event) => {
          const start = touchStart.current;
          touchStart.current = null;
          if (!start) return;
          const dx = event.changedTouches[0].clientX - start.x;
          const dy = event.changedTouches[0].clientY - start.y;
          if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) go(step + (dx < 0 ? 1 : -1));
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") go(step + 1);
          if (event.key === "ArrowLeft") go(step - 1);
        }}
      >
        {/* 장이 바뀔 때마다 그림과 문장을 함께 새로 띄운다 */}
        <div key={step} className="flex flex-1 flex-col items-center motion-safe:animate-[fadeInUp_0.35s_ease]">
          <div className="flex w-full flex-1 items-center justify-center">
            <img
              src={slide.image}
              alt={slide.alt}
              // 그림의 흰 바탕이 화면 배경과 경계 없이 섞이게 한다.
              className="aspect-square w-full max-w-[340px] object-contain mix-blend-multiply"
              draggable={false}
            />
          </div>
          <h1 className="mt-6 whitespace-pre-line text-center text-[19px] font-semibold leading-[1.5] tracking-tight text-slate-800">
            {slide.title}
          </h1>
        </div>

        {/* 진행 표시. 지금 장은 길게 */}
        <div aria-hidden="true" className="mt-6 flex justify-center gap-1.5">
          {SLIDES.map((item, index) => (
            <span
              key={item.image}
              className={`h-1.5 rounded-full transition-colors ${index === step ? "w-6 bg-primary-500" : "w-1.5 bg-slate-200"}`}
            />
          ))}
        </div>

        {/* 왼쪽: 건너뛰기(첫 장) 또는 이전, 오른쪽: 다음 또는 시작 */}
        <div className="mt-8 flex items-center justify-between">
          {step === 0 ? (
            <button type="button" onClick={finish} className="min-h-11 px-1 text-caption text-slate-400">
              건너뛰기
            </button>
          ) : (
            <button
              type="button"
              onClick={() => go(step - 1)}
              aria-label="이전"
              className="grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-500"
            >
              <ArrowLeft aria-hidden="true" className="h-5 w-5" />
            </button>
          )}
          {last ? (
            <button
              type="button"
              onClick={finish}
              className="flex h-12 items-center gap-1.5 rounded-full bg-primary-500 px-6 text-body2 font-semibold text-white shadow-primary"
            >
              {again ? "확인" : "시작"}
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </button>
          ) : (
            <div className="flex items-center gap-3">
              {step > 0 && (
                <button type="button" onClick={finish} className="min-h-11 px-1 text-caption text-slate-400">
                  건너뛰기
                </button>
              )}
              <button
                type="button"
                onClick={() => go(step + 1)}
                aria-label="다음"
                className="grid h-12 w-12 place-items-center rounded-full bg-primary-500 text-white shadow-primary"
              >
                <ArrowRight aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  );
}

export default IntroPage;
