const ACCESS_KEY = "accessToken";
const REFRESH_KEY = "refreshToken";

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);

export const setTokens = (access: string, refresh: string) => {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
};

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith("hwadam.search-view.")) sessionStorage.removeItem(key);
    }
  } catch { /* Browser storage can be disabled. */ }
};
