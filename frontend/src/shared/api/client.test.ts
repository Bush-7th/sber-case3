import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setSession } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  setSession(null);
});
describe("transport guarantees", () => {
  it.each([
    ["specialist", "specialist"],
    ["administrator", "admin"],
  ])("logs in using INF01 and maps role %s to %s", async (serverRole, uiRole) => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      user: { id: "user-id", display_name: "User", role: serverRole },
      expires_at: "2026-10-10T20:00:00Z",
      csrf_token: "csrf",
    }), { status: 200 }));
    vi.stubGlobal("fetch", transport);
    await expect(api.login("username", "password")).resolves.toEqual({
      user: { id: "user-id", name: "User", role: uiRole },
      csrf_token: "csrf",
    });
    expect(JSON.parse(transport.mock.calls[0][1].body)).toEqual({
      username: "username", password: "password",
    });
  });
  it("returns to login when INF01 has no recovery endpoint, without hiding outages", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 405 }))
      .mockResolvedValueOnce(new Response(null, { status: 503 })));
    await expect(api.session()).resolves.toBeNull();
    await expect(api.session()).rejects.toMatchObject({ status: 503 });
  });
  it("rejects malformed success rather than accepting unverifiable data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ items: [{ id: "x" }] }), {
            status: 200,
          }),
        ),
    );
    await expect(api.programs()).rejects.toMatchObject({
      code: "CONTRACT_MISMATCH",
    });
  });
  it("uses one supplied idempotency key and expected revision for upload retries", async () => {
    const transport = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", transport);
    setSession({
      user: { id: "u", name: "Specialist", role: "specialist" },
      csrf_token: "csrf",
    });
    await expect(
      api.upload("package/id", 4, [], "same-key"),
    ).rejects.toBeInstanceOf(ApiError);
    await expect(
      api.upload("package/id", 4, [], "same-key"),
    ).rejects.toBeInstanceOf(ApiError);
    for (const [url, options] of transport.mock.calls) {
      expect(url).toContain("package%2Fid");
      expect(options.headers.get("Idempotency-Key")).toBe("same-key");
      expect(options.headers.get("X-CSRF-Token")).toBe("csrf");
      expect(options.headers.has("Content-Type")).toBe(false);
      expect(options.body.get("expected_revision")).toBe("4");
      expect(options.credentials).toBe("same-origin");
    }
  });
  it("keeps null monetary facts and source references instead of converting them to zero", async () => {
    const { fieldSchema } = await import("./contracts");
    const field = fieldSchema.parse({
      key: "amount",
      label: "Сумма",
      value: null,
      known_state: "missing",
      sources: [],
    });
    expect(field.value).toBeNull();
  });
  it("reuses a JSON command key after an unknown outcome, then releases it after success", async () => {
    const transport = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", transport);
    await expect(api.logout()).rejects.toBeInstanceOf(ApiError);
    await api.logout();
    await api.logout();
    const keys = transport.mock.calls.map(([, options]) =>
      options.headers.get("Idempotency-Key"),
    );
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[1]);
  });
});
