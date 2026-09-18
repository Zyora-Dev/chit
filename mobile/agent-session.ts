export const ACCESS = "zchit_agent_access";
export const REFRESH = "zchit_agent_refresh";

type TokenStore = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
};

export function createBackgroundStore(store: TokenStore & { deleteItemAsync(key: string): Promise<void> }) {
  const prepared = new Set<string>();
  let pending: Promise<unknown> = Promise.resolve();
  function serial<Result>(operation: () => Promise<Result>): Promise<Result> {
    const result = pending.then(operation);
    pending = result.catch(() => undefined);
    return result;
  }
  return {
    getItemAsync: (key: string) => serial(async () => {
      const value = await store.getItemAsync(key);
      if (value && (key === ACCESS || key === REFRESH) && !prepared.has(key)) {
        await store.setItemAsync(key, value);
        prepared.add(key);
      }
      return value;
    }),
    setItemAsync: (key: string, value: string) => serial(async () => {
      await store.setItemAsync(key, value);
      prepared.add(key);
    }),
    deleteItemAsync: (key: string) => serial(async () => {
      await store.deleteItemAsync(key);
      prepared.delete(key);
    }),
  };
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function createAgentClient(baseUrl: string, store: TokenStore, transport: typeof fetch = fetch) {
  let renewal: Promise<string> | null = null;

  async function send(path: string, init: RequestInit, access: string | null) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (access) headers.set("Authorization", `Bearer ${access}`);
    try {
      const response = await transport(`${baseUrl}${path}`, { ...init, headers, signal: controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new ApiError(typeof data.detail === "string" ? data.detail : "Request failed. Please try again.", response.status);
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function renew(failedAccess: string | null) {
    if (renewal) return renewal;
    renewal = (async () => {
      const current = await store.getItemAsync(ACCESS);
      if (current && current !== failedAccess) return current;
      const refresh = await store.getItemAsync(REFRESH);
      if (!refresh) throw new ApiError("Please sign in again to resume location sharing.", 401);
      const tokens = await send("/api/v1/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: refresh }) }, null);
      if (!tokens.access_token || !tokens.refresh_token) throw new Error("Invalid session renewal response.");
      await store.setItemAsync(REFRESH, tokens.refresh_token);
      await store.setItemAsync(ACCESS, tokens.access_token);
      return tokens.access_token as string;
    })();
    try {
      return await renewal;
    } finally {
      renewal = null;
    }
  }

  return async function request(path: string, init: RequestInit = {}, authenticated = true) {
    const access = authenticated ? await store.getItemAsync(ACCESS) : null;
    try {
      return await send(path, init, access);
    } catch (reason) {
      if (!authenticated || !(reason instanceof ApiError) || reason.status !== 401) throw reason;
      return send(path, init, await renew(access));
    }
  };
}