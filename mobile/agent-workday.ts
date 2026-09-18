import { ApiError } from "./agent-session";

export const WORKDAY = "zchit_agent_workday";
const PENDING_LOCATIONS = "zchit_agent_pending_locations";
export type Position = { latitude: number; longitude: number; accuracy_meters: number; device_recorded_at: string; is_mocked: boolean };
type Shift = { shift_id: number; checked_in_at: string };
type AgentStatus = { shift_active: boolean; shift_id: number | null; checked_in_at: string | null; employee_name: string };
type Store = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
};
type Service = { available(): Promise<boolean>; start(): Promise<void>; stop(): Promise<void> };
type Request = (path: string, init?: RequestInit) => Promise<any>;

export function createWorkday(store: Store, request: Request, service: Service) {
  let pending: Promise<unknown> = Promise.resolve();
  function serial<Result>(operation: () => Promise<Result>): Promise<Result> {
    const result = pending.then(operation);
    pending = result.catch(() => undefined);
    return result;
  }
  async function savedShift(): Promise<Shift | null> {
    const saved = await store.getItemAsync(WORKDAY);
    return saved ? JSON.parse(saved) : null;
  }
  async function saveStatus(status: AgentStatus) {
    const previous = await savedShift();
    if (previous && previous.shift_id !== status.shift_id) await store.deleteItemAsync(PENDING_LOCATIONS);
    await store.setItemAsync(WORKDAY, JSON.stringify(status.shift_active ? { shift_id: status.shift_id, checked_in_at: status.checked_in_at } : null));
    if (!status.shift_active) {
      await store.deleteItemAsync(PENDING_LOCATIONS);
      await service.stop();
    }
    return status;
  }
  async function synchronize() {
    return saveStatus(await request("/api/v1/agent/status"));
  }
  async function points(): Promise<Position[]> {
    const saved = await store.getItemAsync(PENDING_LOCATIONS);
    if (!saved) return [];
    try { return JSON.parse(saved); } catch { return []; }
  }
  async function savePoints(values: Position[]) {
    if (values.length) await store.setItemAsync(PENDING_LOCATIONS, JSON.stringify(values.slice(-200)));
    else await store.deleteItemAsync(PENDING_LOCATIONS);
  }
  async function drain(point?: Position) {
    if (await store.getItemAsync(WORKDAY) === null) await synchronize();
    const shift = await savedShift();
    if (!shift) return;
    const queued = await points();
    if (point) queued.push(point);
    const cutoff = Math.max(Date.parse(shift.checked_in_at) - 15000, Date.now() - 24 * 60 * 60 * 1000);
    const valid = queued.filter(value => Date.parse(value.device_recorded_at) >= cutoff).slice(-200);
    await savePoints(valid);
    for (const value of valid.slice(-10).reverse()) {
      try {
        await request("/api/v1/agent/location", { method: "POST", body: JSON.stringify(value) });
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 409) {
          await synchronize();
          return;
        }
        if (!(reason instanceof ApiError) || reason.status !== 422) return;
      }
      valid.splice(valid.indexOf(value), 1);
      await savePoints(valid);
    }
  }
  return {
    savedShift,
    signIn: (saveTokens: () => Promise<void>) => serial(async () => {
      try {
        await saveTokens();
        await synchronize();
      } catch (reason) {
        await store.deleteItemAsync(WORKDAY);
        await store.deleteItemAsync(PENDING_LOCATIONS);
        throw reason;
      }
    }),
    status: () => serial(synchronize),
    resume: () => serial(async () => { if (await savedShift()) await service.start(); }),
    upload: (point: Position) => serial(() => drain(point)),
    flush: () => serial(() => drain()),
    checkIn: (position: () => Promise<Position>) => serial(async () => {
      if (!await service.available()) throw new Error("Background tracking is unavailable. Use the installed zChit Agent app.");
      const point = await position();
      try {
        const shift = await request("/api/v1/agent/check-in", { method: "POST", body: JSON.stringify(point) });
        await saveStatus({ ...shift, shift_active: true, employee_name: "" });
      } catch (reason) {
        const status = await synchronize().catch(() => null);
        if (!status?.shift_active) throw reason;
      }
      await service.start();
    }),
    checkOut: (position: () => Promise<Position>) => serial(async () => {
      const point = await position();
      try {
        await request("/api/v1/agent/check-out", { method: "POST", body: JSON.stringify(point) });
      } catch (reason) {
        const status = await synchronize().catch(() => null);
        if (!status || status.shift_active) throw reason;
        return;
      }
      await saveStatus({ shift_active: false, shift_id: null, checked_in_at: null, employee_name: "" });
    }),
    assertCanLogout: () => serial(async () => {
      if (await savedShift()) throw new Error("Your workday is still open. Check out from Home to close the day before logging out.");
      const status = await synchronize();
      if (status.shift_active) throw new Error("Your workday is still open. Check out from Home to close the day before logging out.");
    }),
  };
}