import { getAccessToken } from "./auth";

const PREFIX = "hwadam.search-view.v1:";

// Use the account identity, not the rotating access token. This only partitions
// cached UI state; authentication is still checked by the server.
export function searchViewKey(entryKey: string): string {
  const token = getAccessToken() ?? "";
  let owner = token;
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(payload));
    if (typeof claims.sub === "string") owner = claims.sub;
  } catch { /* Opaque tokens stay isolated by token. */ }
  return PREFIX + JSON.stringify([owner, entryKey]);
}

export function readSearchView<T>(key: string): T | undefined {
  try {
    const serialized = sessionStorage.getItem(key);
    return serialized ? JSON.parse(serialized) as T : undefined;
  } catch { return undefined; }
}

export function writeSearchView(key: string, view: unknown) {
  try {
    // Keep at most twenty navigation entries in this tab.
    const keys = Object.keys(sessionStorage).filter(item => item.startsWith(PREFIX) && item !== key);
    while (keys.length >= 20) sessionStorage.removeItem(keys.shift()!);
    sessionStorage.setItem(key, JSON.stringify(view));
  } catch { /* Memory restoration still works if browser storage is full. */ }
}

export function deleteSearchView(key: string) {
  try { sessionStorage.removeItem(key); } catch { /* Storage can be disabled. */ }
}
