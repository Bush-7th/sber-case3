import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setSession } from "./client";
import { contextToWire } from "./adapters";
import { draft, evidence, file, ids, item, pageOf, requested, run, session } from "../../../tests/fixtures";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const authenticate = () => setSession({ user: { id: ids.user, name: "User", role: "specialist" }, csrf_token: session.csrf_token });
afterEach(() => { vi.unstubAllGlobals(); setSession(null); });
describe("CON01 transport used by React", () => {
  it.each([["specialist", "specialist"], ["administrator", "admin"]])("maps server role %s to %s", async (serverRole, uiRole) => {
    const transport = vi.fn().mockResolvedValue(json({ ...session, user: { ...session.user, role: serverRole } }));
    vi.stubGlobal("fetch", transport);
    await expect(api.login("username", "password")).resolves.toMatchObject({ user: { name: session.user.display_name, role: uiRole } });
    expect(await (transport.mock.calls[0][0] as Request).json()).toEqual({ username: "username", password: "password" });
  });
  it("recovers the session and CSRF using a cookie-backed GET", async () => {
    const fetch = vi.fn().mockResolvedValue(json(session)); vi.stubGlobal("fetch", fetch);
    await expect(api.session()).resolves.toMatchObject({ user: { role: "specialist" }, csrf_token: session.csrf_token });
    const request = fetch.mock.calls[0][0] as Request;
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/v1/sessions");
    expect(request.credentials).toBe("same-origin");
  });
  it("rejects malformed success and keeps dependency errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json({ items: [{ id: "x" }] })).mockResolvedValueOnce(json({ code: "dependency_unavailable", message: "Unavailable", correlation_id: ids.correlation, details: { dependency: "database" } }, 503)));
    await expect(api.programs()).rejects.toMatchObject({ code: "CONTRACT_MISMATCH" });
    await expect(api.programs()).rejects.toMatchObject({ status: 503, details: { dependency: "database" }, correlationId: ids.correlation });
  });
  it("preserves multipart revision, filenames, CSRF and upload key on retry", async () => {
    authenticate();
    const transport = vi.fn().mockRejectedValue(new TypeError("offline")); vi.stubGlobal("fetch", transport);
    const files = [new File([], "source.pdf")];
    await expect(api.upload(ids.package, 4, files, "same-key")).rejects.toBeInstanceOf(ApiError);
    await expect(api.upload(ids.package, 4, files, "same-key")).rejects.toBeInstanceOf(ApiError);
    for (const [input] of transport.mock.calls) {
      const request = input as Request;
      expect(request.url).toContain(ids.package);
      expect(request.headers.get("Idempotency-Key")).toBe("same-key");
      expect(request.headers.get("X-CSRF-Token")).toBe(session.csrf_token);
      expect(request.headers.get("Content-Type")).toMatch(/^multipart\/form-data; boundary=/);
      const form = await request.formData(); expect(form.get("expected_revision")).toBe("4");
      expect((form.get("files") as File).name).toBe("source.pdf");
      expect(request.credentials).toBe("same-origin");
    }
  });
  it("uses offset pagination and preserves explicit report/decision freshness", async () => {
    const transport = vi.fn().mockResolvedValue(json(pageOf([{ ...item, report_freshness: "outdated", decision_status: "accepted", decision_freshness: "outdated" }], 25, 50)));
    vi.stubGlobal("fetch", transport);
    const data = await api.packages(25);
    const url = new URL((transport.mock.calls[0][0] as Request).url);
    expect(url.searchParams.get("offset")).toBe("25"); expect(url.searchParams.has("cursor")).toBe(false);
    expect(data.items[0]).toMatchObject({ report_freshness: "outdated", decision_status: "accepted", decision_freshness: "outdated", file_count: null });
  });
  it("sends boolean/null context with extra known conditions preserved", async () => {
    const context = { project_type: "", certificate_required: "unknown" as const, gims_required: "false" as const, conditions: { another_condition: true } };
    expect(contextToWire(context)).toEqual({ project_type: null, conditions: { another_condition: true, certificate_required: null, gims_required: false } });
    authenticate(); const transport = vi.fn().mockResolvedValueOnce(json(item, 201)).mockResolvedValueOnce(json(requested, 202)); vi.stubGlobal("fetch", transport);
    await api.createPackage({ title: "Title", program_id: ids.program, program_version_id: ids.version, context });
    const body = await (transport.mock.calls[0][0] as Request).json();
    expect(Object.keys(body).sort()).toEqual(["program_version_id", "project_context", "title"]);
    await expect(api.configure(ids.package, { expected_revision: 2, program_version_id: ids.version, context })).resolves.toMatchObject({ input_revision: 3 });
  });
  it("maps run counters, file IDs, unknown facts and vision sources without a fabricated zero", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(run)));
    const data = await api.run(ids.run);
    expect(data.progress).toEqual({ accepted: 1, running: 0, terminal: 1 });
    expect(data.files[0]).toMatchObject({ id: ids.file, file_version_id: ids.fileVersion });
    expect(data.document_units[0].fields[0].value).toBeNull();
    expect(data.report?.rules[0].sources[0]).toMatchObject({ file_id: ids.file, file_version_id: ids.fileVersion, page: 2, method: evidence.extraction_method });
    expect(data.report?.requirements[1].severity).toBe("info");
  });
  it("sends fragment IDs for grouping and a package-wide verification command", async () => {
    authenticate(); const transport = vi.fn().mockImplementation(() => json(requested, 202)); vi.stubGlobal("fetch", transport);
    await api.grouping(ids.document, 2, [ids.fragment], "Reason"); await api.verify(ids.package, 2);
    expect(await (transport.mock.calls[0][0] as Request).json()).toEqual({ expected_revision: 2, fragment_ids: [ids.fragment], reason: "Reason" });
    expect(await (transport.mock.calls[1][0] as Request).json()).toEqual({ expected_revision: 2 });
  });
  it("marks a report from a different revision as outdated", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ ...run, report: { ...run.report, input_revision: 1 } })));
    await expect(api.run(ids.run)).resolves.toMatchObject({ freshness: "outdated" });
  });
  it("preserves a complete admin definition including compound predicates", async () => {
    authenticate(); const transport = vi.fn().mockResolvedValue(json(draft)); vi.stubGlobal("fetch", transport);
    const saved = await api.saveDraft(draft);
    const body = await (transport.mock.calls[0][0] as Request).json();
    expect(body).toEqual({ expected_revision: 1, definition: saved.definition });
    expect(saved.definition.requirements[1].predicate).toEqual(draft.definition.requirements[1].predicate);
    expect(saved.definition.rules[0].bindings).toEqual(draft.definition.rules[0].bindings);
  });
  it("reuses a command key for an ambiguous outcome and releases it after success", async () => {
    authenticate(); const transport = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(new Response(null, { status: 204 })); vi.stubGlobal("fetch", transport);
    await expect(api.logout()).rejects.toBeInstanceOf(ApiError); await api.logout(); await api.logout();
    const keys = transport.mock.calls.map(([request]) => (request as Request).headers.get("Idempotency-Key"));
    expect(keys[0]).toBe(keys[1]); expect(keys[2]).not.toBe(keys[1]);
  });
  it("maps an upload receipt with accepted metadata and per-file errors", async () => {
    authenticate(); vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ ...requested, accepted: [file], rejected: [{ original_name: "other.pdf", error: { code: "unsupported_format", message: "Unsupported", details: {}, correlation_id: ids.correlation } }] }, 202)));
    await expect(api.upload(ids.package, 2, [], "receipt-key")).resolves.toMatchObject({ accepted: [{ name: file.original_name, file_version_id: ids.fileVersion }], rejected: [{ name: "other.pdf", code: "unsupported_format" }] });
  });
});
