export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

type ValidationDetail = { loc?: Array<string | number>; msg?: string };
type ApiError = { detail?: string | ValidationDetail | ValidationDetail[] };

export function formatApiDetail(detail: ApiError["detail"], fallback = "Something went wrong. Please try again."): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const field = item.loc?.filter((part) => part !== "body").join(" → ");
      return field ? `${field}: ${item.msg ?? "Invalid value"}` : item.msg ?? "Invalid value";
    }).join(". ");
  }
  if (detail && typeof detail === "object") return detail.msg ?? fallback;
  return fallback;
}

export async function getResponseError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => ({})) as ApiError;
  return formatApiDetail(body.detail, fallback);
}

export class ApiRequestError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function clearSession() { localStorage.removeItem("zchit_access_token"); localStorage.removeItem("zchit_refresh_token"); }
export function saveSession(tokens: { access_token: string; refresh_token?: string | null }) { localStorage.setItem("zchit_access_token", tokens.access_token); if (tokens.refresh_token) localStorage.setItem("zchit_refresh_token", tokens.refresh_token); }

export async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  const data = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    throw new ApiRequestError(formatApiDetail(data.detail), response.status);
  }
  return data;
}

export async function authenticatedApiRequest<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const token = localStorage.getItem("zchit_access_token");
  try { return await apiRequest<T>(path, { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } }); }
  catch (error) {
    if (!(error instanceof ApiRequestError) || error.status !== 401 || !retry) throw error;
    const refreshToken=localStorage.getItem("zchit_refresh_token"); if(!refreshToken){clearSession();throw error;}
    try { const tokens=await apiRequest<{access_token:string;refresh_token:string}>("/api/v1/auth/refresh",{method:"POST",body:JSON.stringify({refresh_token:refreshToken})});saveSession(tokens);return authenticatedApiRequest<T>(path,init,false); }
    catch { clearSession(); window.location.replace("/login"); throw error; }
  }
}
