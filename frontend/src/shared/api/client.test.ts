import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setSession } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  setSession(null);
});
describe("transport guarantees", () => {
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
