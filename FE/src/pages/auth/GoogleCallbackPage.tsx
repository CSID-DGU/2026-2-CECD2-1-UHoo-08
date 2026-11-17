import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { googleLogin } from "../../api/authApi";
import { setTokens } from "../../lib/auth";
import { consumeGoogleState } from "../../lib/googleAuth";

export function GoogleCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;
    const fail = (loginError: string) =>
      navigate("/", { replace: true, state: { loginError } });

    async function completeLogin() {
      try {
        if (!consumeGoogleState(searchParams.get("state"))) {
          fail("로그인 요청을 확인할 수 없습니다. 다시 시도해 주세요.");
          return;
        }
        if (searchParams.has("error")) {
          fail(searchParams.get("error") === "access_denied"
            ? "Google 로그인이 취소되었습니다."
            : "Google 로그인에 실패했습니다. 다시 시도해 주세요.");
          return;
        }
        const code = searchParams.get("code");
        if (!code) {
          fail("Google 인증 코드가 없습니다. 다시 로그인해 주세요.");
          return;
        }
        const { data } = await googleLogin(code);
        setTokens(data.accessToken, data.refreshToken);
        navigate(data.isNewUser ? "/onboarding/profile" : "/home", { replace: true });
      } catch (error) {
        const code = (error as { error?: { code?: string } } | null)?.error?.code;
        fail(code === "EMAIL_ALREADY_EXISTS"
          ? "이미 다른 로그인 방식으로 가입한 이메일입니다. 기존 로그인 방식을 이용해 주세요."
          : "Google 로그인에 실패했습니다. 다시 시도해 주세요.");
      }
    }
    void completeLogin();
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p role="status" className="text-body2 text-gray-400">로그인 중...</p>
    </div>
  );
}
