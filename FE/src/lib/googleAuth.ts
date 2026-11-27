const STATE_KEY = "hwadam.google-oauth-state";

export function startGoogleLogin() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
  if (!clientId) throw new Error("Google 로그인 설정이 준비되지 않았습니다.");
  const state = crypto.randomUUID();
  sessionStorage.setItem(STATE_KEY, state);
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: import.meta.env.VITE_GOOGLE_REDIRECT_URI?.trim() || `${window.location.origin}/auth/google`,
    response_type: "code",
    scope: "openid email profile",
    state,
  });
  window.location.assign(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
}

export function consumeGoogleState(state: string | null): boolean {
  const expected = sessionStorage.getItem(STATE_KEY);
  sessionStorage.removeItem(STATE_KEY);
  return !!state && !!expected && state === expected;
}
