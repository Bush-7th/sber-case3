import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiError, MissingCsrfTokenError, createApiClient } from "../src/shared/api/index.js";

const packageId = "11111111-1111-4111-8111-111111111111";
const correlationId = "22222222-2222-4222-8222-222222222222";

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/json", "X-Correlation-ID": correlationId },
  });
}

test("upload uses multipart files, revision, idempotency, session and CSRF", async () => {
  let observed = false;
  const api = createApiClient({
    baseUrl: "https://case3.example", getCsrfToken: () => "csrf-value",
    fetch: async (input) => {
      const request = input as Request;
      assert.equal(request.method, "POST");
      assert.equal(request.credentials, "same-origin");
      assert.equal(request.headers.get("X-CSRF-Token"), "csrf-value");
      assert.equal(request.headers.get("Idempotency-Key"), "upload-key");
      assert.match(request.headers.get("Content-Type") ?? "", /^multipart\/form-data; boundary=/);
      const body = await request.formData();
      assert.equal(body.get("expected_revision"), "7");
      assert.equal(body.getAll("files").length, 2);
      observed = true;
      return json({
        package_id: packageId, input_revision: 7, accepted: [], rejected: [
          { original_name: "blob", error: {
            code: "empty_file", message: "Файл пуст.", details: {}, correlation_id: correlationId,
          } },
          { original_name: "blob", error: {
            code: "empty_file", message: "Файл пуст.", details: {}, correlation_id: correlationId,
          } },
        ],
        run_id: null, correlation_id: correlationId,
      }, 202);
    },
  });
  // Empty in-memory blobs test transport only; no sample documents or OCR calls are made.
  const response = await api.uploadFiles(packageId, [new Blob([]), new Blob([])], 7, "upload-key");
  assert.equal(response.data?.input_revision, 7);
  assert.ok(observed);
});

test("JSON commands preserve expected revision and get CSRF automatically", async () => {
  const api = createApiClient({
    baseUrl: "https://case3.example", getCsrfToken: () => "csrf-value",
    fetch: async (input) => {
      const request = input as Request;
      assert.equal(request.headers.get("X-CSRF-Token"), "csrf-value");
      assert.equal(request.headers.get("Idempotency-Key"), "run-key");
      assert.deepEqual(await request.json(), { expected_revision: 3 });
      return json({ package_id: packageId, input_revision: 3, run_id: packageId, correlation_id: correlationId }, 202);
    },
  });
  await api.http.POST("/api/v1/packages/{package_id}/verification-runs", {
    params: { path: { package_id: packageId }, header: { "Idempotency-Key": "run-key" } },
    body: { expected_revision: 3 },
  });
});

test("login needs no prior CSRF; mutations cannot proceed without one", async () => {
  let calls = 0;
  const api = createApiClient({
    baseUrl: "https://case3.example", getCsrfToken: () => undefined,
    fetch: async (input) => {
      assert.equal((input as Request).headers.get("X-CSRF-Token"), null);
      calls += 1;
      return json({ user: { id: packageId, display_name: "User", role: "specialist" },
        expires_at: "2026-10-10T12:00:00Z", csrf_token: "new-token" });
    },
  });
  await api.http.POST("/api/v1/sessions", { body: { username: "user", password: "test-only" } });
  await assert.rejects(api.http.DELETE("/api/v1/sessions"), MissingCsrfTokenError);
  assert.equal(calls, 1);
});

test("binary downloads are blobs; errors retain code, details and correlation", async () => {
  let fail = false;
  const api = createApiClient({
    baseUrl: "https://case3.example", getCsrfToken: () => undefined,
    fetch: async () => fail
      ? json({ code: "revision_conflict", message: "Ревизия изменилась.", details: { actual_revision: 2 },
        correlation_id: correlationId }, 409)
      : new Response(new Uint8Array([1, 2]), { headers: { "Content-Type": "application/octet-stream" } }),
  });
  const downloaded = await api.downloadFile(packageId);
  assert.ok(downloaded.data instanceof Blob);
  assert.equal(downloaded.data.size, 2);
  fail = true;
  await assert.rejects(api.downloadFile(packageId), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 409);
    assert.equal(error.code, "revision_conflict");
    assert.equal(error.correlationId, correlationId);
    assert.deepEqual(error.details, { actual_revision: 2 });
    return true;
  });
});

test("non-JSON proxy errors have a safe message and correlation", async () => {
  const api = createApiClient({
    baseUrl: "https://case3.example", getCsrfToken: () => undefined,
    fetch: async () => new Response("upstream internal detail", {
      status: 502, headers: { "X-Correlation-ID": correlationId },
    }),
  });
  await assert.rejects(api.downloadFile(packageId), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.correlationId, correlationId);
    assert.equal(error.code, "http_error");
    assert.doesNotMatch(error.message, /upstream/);
    return true;
  });
});
