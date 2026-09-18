import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { ACCESS, REFRESH, ApiError, createAgentClient, createBackgroundStore } from "./agent-session.ts";

const compiled = ts.transpileModule(readFileSync(new URL("./agent-workday.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const workdayModule = { exports: {} };
runInNewContext(compiled.outputText, { exports: workdayModule.exports, require: () => ({ ApiError }), Date, JSON, Error });
const { createWorkday, WORKDAY } = workdayModule.exports;

function tokenStore() {
  const values = new Map([[ACCESS, "expired"], [REFRESH, "refresh-1"]]);
  return {
    values,
    async getItemAsync(key) { return values.get(key) ?? null; },
    async setItemAsync(key, value) { values.set(key, value); },
    async deleteItemAsync(key) { values.delete(key); },
  };
}
const response = (body, status = 200) => Response.json(body, { status });

test("simultaneous foreground/background requests rotate refresh once and retry", async () => {
  const store = tokenStore();
  let rotations = 0;
  const client = createAgentClient("https://agent.test", store, async (url, init) => {
    if (url.endsWith("/refresh")) {
      rotations++;
      assert.equal(JSON.parse(init.body).refresh_token, "refresh-1");
      return response({ access_token: "renewed", refresh_token: "refresh-2" });
    }
    return init.headers.get("Authorization") === "Bearer renewed" ? response({ ok: true }) : response({}, 401);
  });
  const results = await Promise.all(Array.from({ length: 8 }, () => client("/api/v1/agent/location", { method: "POST", body: "{}" })));
  assert.equal(rotations, 1);
  assert.ok(results.every(result => result.ok));
  assert.equal(store.values.get(ACCESS), "renewed");
  assert.equal(store.values.get(REFRESH), "refresh-2");
  await client("/api/v1/agent/status");
  assert.equal(rotations, 1);
});

test("network failure during renewal preserves credentials and allows recovery", async () => {
  const store = tokenStore();
  let offline = true;
  const client = createAgentClient("https://agent.test", store, async (url, init) => {
    if (url.endsWith("/refresh")) {
      if (offline) throw new TypeError("Network unavailable");
      return response({ access_token: "renewed", refresh_token: "refresh-2" });
    }
    return init.headers.get("Authorization") === "Bearer renewed" ? response({ ok: true }) : response({}, 401);
  });
  await assert.rejects(client("/api/v1/agent/location"), /Network unavailable/);
  assert.equal(store.values.get(REFRESH), "refresh-1");
  assert.equal(store.values.get(ACCESS), "expired");
  offline = false;
  assert.equal((await client("/api/v1/agent/location")).ok, true);
});

test("invalid credentials fail without looping or deleting session state", async () => {
  const store = tokenStore();
  let calls = 0;
  const client = createAgentClient("https://agent.test", store, async () => { calls++; return response({ detail: "Invalid refresh token" }, 401); });
  await assert.rejects(client("/api/v1/agent/status"), reason => reason instanceof ApiError && reason.status === 401);
  assert.equal(calls, 2);
  assert.equal(store.values.get(REFRESH), "refresh-1");
});

test("login is unauthenticated and does not try to renew rejected credentials", async () => {
  const store = tokenStore();
  let calls = 0;
  const client = createAgentClient("https://agent.test", store, async (_url, init) => {
    calls++;
    assert.equal(init.headers.has("Authorization"), false);
    return response({}, 401);
  });
  await assert.rejects(client("/api/v1/auth/login", { method: "POST" }, false), ApiError);
  assert.equal(calls, 1);
});

function trackingFixture() {
  const store = tokenStore();
  const state = { active: false, offline: false, available: true, starts: 0, stops: 0, uploads: [], shiftId: 7, lostResponse: false };
  const checkedInAt = new Date(Date.now() - 60000).toISOString();
  const request = async (path, init) => {
    if (state.offline) throw new TypeError("Offline");
    if (path.endsWith("/check-in")) state.active = true;
    if (path.endsWith("/check-out")) state.active = false;
    if (state.lostResponse && (path.endsWith("/check-in") || path.endsWith("/check-out"))) throw new TypeError("Response lost");
    if (path.endsWith("/location")) state.uploads.push(JSON.parse(init.body));
    return { shift_active: state.active, shift_id: state.active ? state.shiftId : null, checked_in_at: checkedInAt, employee_name: "Agent" };
  };
  const service = {
    async available() { return state.available; },
    async start() { state.starts++; },
    async stop() { state.stops++; },
  };
  return { store, state, workday: createWorkday(store, request, service), reopen: () => createWorkday(store, request, service) };
}
const position = () => Promise.resolve({ latitude: 8.18, longitude: 77.41, accuracy_meters: 10, device_recorded_at: new Date().toISOString(), is_mocked: false });

test("open workday persists on reopen offline; logout and failed checkout cannot stop it", async () => {
  const { workday, state, store, reopen } = trackingFixture();
  await workday.checkIn(position);
  assert.equal(state.starts, 1);
  state.offline = true;
  const reopened = reopen();
  await reopened.resume();
  assert.equal(state.starts, 2);
  await assert.rejects(reopened.assertCanLogout(), /workday is still open/);
  await assert.rejects(reopened.checkOut(position), /Offline/);
  assert.equal(state.stops, 0);
  assert.equal(JSON.parse(store.values.get(WORKDAY)).shift_id, 7);
});

test("successful checkout stops sharing and later callbacks do not upload", async () => {
  const { workday, state, store } = trackingFixture();
  await workday.checkIn(position);
  await workday.checkOut(position);
  assert.equal(state.stops, 1);
  assert.equal(store.values.get(WORKDAY), "null");
  await workday.upload(await position());
  assert.equal(state.uploads.length, 0);
  await workday.assertCanLogout();
});

test("offline points survive concurrent callbacks and replay newest first", async () => {
  const { workday, state } = trackingFixture();
  await workday.checkIn(position);
  state.offline = true;
  const first = { ...await position(), latitude: 8.19 };
  const second = { ...await position(), latitude: 8.20 };
  await Promise.all([workday.upload(first), workday.upload(second)]);
  state.offline = false;
  await workday.flush();
  assert.deepEqual(state.uploads.map(point => point.latitude), [8.20, 8.19]);
});

test("unavailable background tracking prevents check-in", async () => {
  const { workday, state } = trackingFixture();
  state.available = false;
  await assert.rejects(workday.checkIn(position), /Background tracking is unavailable/);
  assert.equal(state.active, false);
  assert.equal(state.starts, 0);
});

test("logout checks the server even without local workday state", async () => {
  const { workday, state } = trackingFixture();
  state.active = true;
  await assert.rejects(workday.assertCanLogout(), /workday is still open/);
  assert.equal(state.stops, 0);
});

test("lost successful shift responses reconcile with the server", async () => {
  const { workday, state, store } = trackingFixture();
  state.lostResponse = true;
  await workday.checkIn(position);
  assert.equal(state.starts, 1);
  assert.equal(JSON.parse(store.values.get(WORKDAY)).shift_id, 7);
  await workday.checkOut(position);
  assert.equal(state.stops, 1);
  assert.equal(store.values.get(WORKDAY), "null");
});

test("sign-in reconciles shift ownership before queued callbacks upload", async () => {
  const { workday, state, store } = trackingFixture();
  await workday.checkIn(position);
  state.offline = true;
  await workday.upload(await position());
  state.offline = false;
  state.shiftId = 8;
  await workday.signIn(async () => {});
  await workday.flush();
  assert.equal(state.uploads.length, 0);
  assert.equal(JSON.parse(store.values.get(WORKDAY)).shift_id, 8);
});

test("failed sign-in reconciliation cannot upload the previous account queue", async () => {
  const { workday, state, store } = trackingFixture();
  await workday.checkIn(position);
  state.offline = true;
  await workday.upload(await position());
  await assert.rejects(workday.signIn(async () => {}), /Offline/);
  assert.equal(store.values.has(WORKDAY), false);
  state.offline = false;
  state.shiftId = 8;
  await workday.flush();
  assert.equal(state.uploads.length, 0);
});

test("existing tokens receive background storage options once per process", async () => {
  const source = tokenStore();
  const writes = [];
  const store = createBackgroundStore({ ...source, async setItemAsync(key, value) { writes.push(key); await source.setItemAsync(key, value); } });
  await Promise.all([store.getItemAsync(ACCESS), store.getItemAsync(REFRESH), store.getItemAsync(ACCESS)]);
  assert.deepEqual(writes, [ACCESS, REFRESH]);
});

test("background storage migration cannot overwrite a concurrent token rotation", async () => {
  const source = tokenStore();
  const store = createBackgroundStore(source);
  await Promise.all([store.getItemAsync(ACCESS), store.setItemAsync(ACCESS, "rotated-access")]);
  assert.equal(await store.getItemAsync(ACCESS), "rotated-access");
  await store.deleteItemAsync(ACCESS);
  assert.equal(await store.getItemAsync(ACCESS), null);
});