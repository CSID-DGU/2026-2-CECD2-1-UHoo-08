import Spline from "@splinetool/react-spline";
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { startGoogleLogin } from "../../lib/googleAuth";
import googleIcon from "../../assets/Google.png";
import kakaoIcon from "../../assets/Kakao.png";
import HwadamLogo from "../../assets/Hwadam.svg";

// 배포 도메인마다 콜백 주소가 달라지므로 현재 origin에서 유도한다.
// 고정이 필요하면 VITE_KAKAO_REDIRECT_URI로 덮어쓸 수 있다.
const KAKAO_REDIRECT_URI =
  import.meta.env.VITE_KAKAO_REDIRECT_URI ||
  `${window.location.origin}/auth/social`;

const KAKAO_AUTH_URL =
  `https://kauth.kakao.com/oauth/authorize` +
  `?client_id=${import.meta.env.VITE_KAKAO_CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(KAKAO_REDIRECT_URI)}` +
  `&response_type=code`;

const COPY = {
  tagline: "피부가 닮은 사람들의 선택으로\n나에게 맞는 화장품을 찾아요",
  kakao: "카카오로 계속하기",
  google: "Google로 계속하기",
  terms: "로그인 시 이용약관 및 개인정보처리방침에 동의합니다",
};

const socialButtons = [
  {
    label: COPY.kakao,
    icon: kakaoIcon,
    className: "bg-kakao",
    onClick: () => {
      window.location.href = KAKAO_AUTH_URL;
    },
  },
  {
    label: COPY.google,
    icon: googleIcon,
    className: "bg-white",
    onClick: startGoogleLogin,
  },
];

export function LoginPage() {
  const location = useLocation();
  const [loginError, setLoginError] = useState<string | null>(
    location.state?.loginError ?? null,
  );
  const handleLogin = (onClick?: () => void) => {
    setLoginError(null);
    try {
      onClick?.();
    } catch (error) {
      setLoginError(
        error instanceof Error
          ? error.message
          : "로그인을 시작할 수 없습니다. 다시 시도해 주세요.",
      );
    }
  };

  return (
    <div className="min-h-dvh">
      <div className="relative mx-auto min-h-dvh w-full max-w-[430px] overflow-hidden">
        {/* <Spline
          className="pointer-events-none absolute left-0 top-0 z-0 h-[calc(100%+80px)] w-full"
          scene="https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode"
        /> */}
        <Spline
          scene="https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "calc(100% + 80px)",
            zIndex: 0,
            pointerEvents: "none",
          }}
        />

        <section className="relative z-10 flex min-h-dvh flex-col">
          <div className="mx-auto pb-10 pt-24">
            <div className="flex items-end justify-between gap-6">
              <img src={HwadamLogo} alt="Hwadam Logo" className="w-25" />
              <h1 className="font-lora text-[48px] font-semibold text-gray-500">Hwadam</h1>
            </div>
            <p className="mt-5 whitespace-pre-line text-center text-body2 leading-6 text-gray-400">
              {COPY.tagline}
            </p>
          </div>

          <div className="px-6">
            <div className="grid gap-3">
              {socialButtons.map(({ label, icon, className, onClick }) => (
                <button
                  className={`relative flex h-[54px] items-center justify-center rounded-xl text-gray-500 ${className}`}
                  key={label}
                  type="button"
                  onClick={() => handleLogin(onClick)}
                >
                  <img
                    alt=""
                    aria-hidden="true"
                    className="absolute left-5 h-5 w-5 object-contain"
                    src={icon}
                  />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {loginError && (
            <p
              role="alert"
              className="mx-6 mt-4 rounded-xl bg-white/90 p-3 text-body2 text-red-700"
            >
              {loginError}
            </p>
          )}
          <div className="mt-auto px-6 pb-6">
            <p className="text-center text-caption text-gray-400">
              {COPY.terms}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
