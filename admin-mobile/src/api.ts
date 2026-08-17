import * as SecureStore from "expo-secure-store";

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const ACCESS_KEY = "zchit_owner_access";
export const REFRESH_KEY = "zchit_owner_refresh";
let sessionExpiredHandler: (() => void) | null = null;
export function setSessionExpiredHandler(handler: (() => void) | null) { sessionExpiredHandler = handler; }

async function errorMessage(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((item: {loc?:Array<string|number>;msg?:string})=>`${item.loc?.filter(part=>part!=="body").join(" → ")??"Field"}: ${item.msg??"Invalid value"}`).join(". ");
  return "Request failed.";
}

export async function publicRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init.headers ?? {}) } });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export async function saveTokens(access: string, refresh?: string | null) {
  await SecureStore.setItemAsync(ACCESS_KEY, access);
  if (refresh) await SecureStore.setItemAsync(REFRESH_KEY, refresh);
}

export async function clearTokens() {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

export async function authRequest<T>(path: string, init: RequestInit = {}, access?: string | null, retry = true): Promise<T> {
  const token = access ?? await SecureStore.getItemAsync(ACCESS_KEY);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init.headers ?? {}), Authorization: `Bearer ${token}` } });
  if (response.ok) return response.json();
  if (response.status === 401 && retry) {
    const refresh = await SecureStore.getItemAsync(REFRESH_KEY);
    if (refresh) {
      try { const rotated = await publicRequest<{ access_token: string; refresh_token: string }>("/api/v1/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: refresh }) });await saveTokens(rotated.access_token, rotated.refresh_token);return authRequest<T>(path, init, rotated.access_token, false); }
      catch { await clearTokens(); sessionExpiredHandler?.(); throw new Error("Session expired. Sign in again."); }
    }
    await clearTokens(); sessionExpiredHandler?.();
  }
  throw new Error(await errorMessage(response));
}
