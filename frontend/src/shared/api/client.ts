import { z } from "zod";
import * as c from "./contracts";
import * as a from "./adapters";
import { ApiError, MissingCsrfTokenError, createApiClient } from "./openapi-client";
import type { components } from "./schema";
type S = components["schemas"];
export { ApiError };
let csrf: string | undefined;
const pendingKeys = new Map<string, string>();
export function setSession(session: c.Session | null) {
  csrf = session?.csrf_token;
  if (!session) pendingKeys.clear();
}
const transport = createApiClient({
  baseUrl: typeof location === "undefined" ? "http://localhost" : location.origin,
  getCsrfToken: () => csrf,
  fetch: (input, init) => globalThis.fetch(input, init),
});
const http = transport.http;
type Result<T> = { data?: T; response: Response };
async function receive<T>(call: Promise<Result<T>>): Promise<T> {
  try {
    const result = await call;
    if (result.response.status === 204) return null as T;
    if (result.data === undefined) throw new ApiError(result.response.status, "INVALID_RESPONSE");
    return result.data;
  } catch (error) {
    if (error instanceof ApiError || error instanceof MissingCsrfTokenError ||
      (error instanceof DOMException && error.name === "AbortError")) throw error;
    throw new ApiError(0, error instanceof SyntaxError ? "INVALID_RESPONSE" : "NETWORK_ERROR");
  }
}
function decode<T, U>(data: T, schema: z.ZodType<U>, adapt: (data: T) => unknown): U {
  try { return schema.parse(adapt(data)); }
  catch { throw new ApiError(200, "CONTRACT_MISMATCH"); }
}
async function command<T, U>(intent: unknown, call: (key: string) => Promise<Result<T>>, decodeResult: (data: T) => U): Promise<U> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(intent)));
  const fingerprint = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
  const key = pendingKeys.get(fingerprint) ?? crypto.randomUUID();
  pendingKeys.set(fingerprint, key);
  try {
    const data = decodeResult(await receive(call(key)));
    pendingKeys.delete(fingerprint);
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) pendingKeys.delete(fingerprint);
    throw error;
  }
}
const pageMeta = z.object({ items: z.array(z.unknown()), total: z.number().int().nonnegative(), offset: z.number().int().nonnegative(), limit: z.number().int().positive() });
function page<T, U>(data: { items: T[]; total: number; offset: number; limit: number }, schema: z.ZodType<U>, adapt: (item: T) => unknown) {
  try {
    const meta = pageMeta.parse(data);
    if (meta.offset < meta.total && !meta.items.length) throw new Error("Non-progressing page");
    return { ...meta, items: data.items.map(item => decode(item, schema, adapt)) };
  } catch { throw new ApiError(200, "CONTRACT_MISMATCH"); }
}
async function allPages<T>(load: (offset: number) => Promise<{ items: T[]; total: number; offset: number; limit: number }>) {
  const items: T[] = [];
  let offset = 0;
  for (;;) {
    const result = await load(offset);
    if (result.offset !== offset) throw new ApiError(200, "CONTRACT_MISMATCH");
    items.push(...result.items);
    offset += result.items.length;
    if (offset >= result.total) return { items, total: result.total, offset: 0, limit: result.limit };
  }
}
const runRequestedSchema = z.object({ input_revision: z.number().int().nonnegative(), run_id: z.string() });
const loginSchema = z.object({ user: z.object({ id: z.string(), display_name: z.string(), role: z.enum(["specialist", "administrator"]) }), expires_at: z.string(), csrf_token: z.string().min(1) });
const versionSchema = z.object({ id: z.string(), program_id: z.string(), version: z.number().int().positive(), published_at: z.string(), definition: a.definitionSchema });
const draftSummarySchema = a.draftSchema.omit({ definition: true, base_version_id: true });
const versionView = (v: S["ProgramVersion"]) => ({ ...v, label: `Редакция ${v.version}` });
async function programs(signal?: AbortSignal) {
  return allPages(async offset => page(await receive(http.GET("/api/v1/programs", { params: { query: { offset, limit: 100 } }, signal })), c.programSchema, p => ({ ...p, description: "" })));
}
async function versions(id: string, signal?: AbortSignal) {
  return allPages(async offset => {
    const result = page(await receive(http.GET("/api/v1/programs/{program_id}/versions", { params: { path: { program_id: id }, query: { offset, limit: 100 } }, signal })), versionSchema, v => v);
    return { ...result, items: result.items.map(versionView) };
  });
}
export const api = {
  // INF01 has no recovery endpoint; no speculative GET is sent.
  session: async (_signal?: AbortSignal): Promise<c.Session | null> => null,
  login: (username: string, password: string) => command(["login", username, password],
    () => http.POST("/api/v1/sessions", { body: { username, password } }),
    data => {
      const s = decode(data, loginSchema, value => value);
      return { user: { id: s.user.id, name: s.user.display_name, role: s.user.role === "administrator" ? "admin" as const : "specialist" as const }, csrf_token: s.csrf_token };
    }),
  logout: () => command(["logout"], key => http.DELETE("/api/v1/sessions", { headers: { "Idempotency-Key": key } }), () => null),
  programs, versions,
  documentTypes: async (programId: string, versionId: string, signal?: AbortSignal) => {
    const version = (await versions(programId, signal)).items.find(v => v.id === versionId);
    if (!version) throw new ApiError(404, "version_not_found");
    return { items: version.definition.document_types.map(t => ({ id: t.id, name: t.label, extension: t.extension ?? false })) };
  },
  packages: async (offset = 0, signal?: AbortSignal) => page(await receive(http.GET("/api/v1/packages", { params: { query: { offset, limit: 25 } }, signal })), c.summarySchema, a.summary),
  package: async (id: string, signal?: AbortSignal) => decode(await receive(http.GET("/api/v1/packages/{package_id}", { params: { path: { package_id: id } }, signal })), c.packageSchema, a.packageDetail),
  createPackage: (body: { title: string; program_id: string; program_version_id: string; context: c.ProjectContext }) => {
    const wire: S["PackageCreate"] = { title: body.title, program_version_id: body.program_version_id, project_context: a.contextToWire(body.context) };
    return command(["createPackage", wire], () => http.POST("/api/v1/packages", { body: wire }), data => decode(data, c.packageSchema, a.packageDetail));
  },
  configure: (id: string, body: { expected_revision: number; program_version_id: string; context: c.ProjectContext }) => {
    const wire: S["ConfigurationUpdate"] = { expected_revision: body.expected_revision, program_version_id: body.program_version_id, project_context: a.contextToWire(body.context) };
    return command(["configure", id, wire], () => http.PATCH("/api/v1/packages/{package_id}/configuration", { params: { path: { package_id: id } }, body: wire }), data => decode(data, runRequestedSchema, value => value));
  },
  upload: async (id: string, revision: number, files: File[], key: string) => decode(await receive(transport.uploadFiles(id, files, revision, key)), c.uploadSchema, data => ({
    input_revision: data.input_revision, run_id: data.run_id,
    accepted: data.accepted.map(f => ({ file_version_id: f.file_version_id, name: f.original_name })),
    rejected: data.rejected.map(r => ({ name: r.original_name, code: r.error.code })) })),
  run: async (id: string, signal?: AbortSignal) => decode(await receive(http.GET("/api/v1/verification-runs/{run_id}", { params: { path: { run_id: id } }, signal })), c.runSchema, a.run),
  verify: (id: string, revision: number) => command(["verify", id, revision], key => http.POST("/api/v1/packages/{package_id}/verification-runs", { params: { path: { package_id: id }, header: { "Idempotency-Key": key } }, body: { expected_revision: revision } }), data => decode(data, runRequestedSchema, value => value)),
  type: (id: string, revision: number, documentType: string, reason: string) => {
    const type = z.enum(["application", "consent", "certificate", "presentation", "cost_justification", "bank_statement", "property_document", "guarantee_letter", "gims_declaration"]).parse(documentType);
    return command(["type", id, revision, type, reason], () => http.PATCH("/api/v1/document-units/{document_id}/type", { params: { path: { document_id: id } }, body: { expected_revision: revision, document_type: type, reason } }), data => decode(data, runRequestedSchema, value => value));
  },
  grouping: (id: string, revision: number, fragmentIds: string[], reason: string) => command(["grouping", id, revision, fragmentIds, reason], () => http.PATCH("/api/v1/document-units/{document_id}/grouping", { params: { path: { document_id: id } }, body: { expected_revision: revision, fragment_ids: fragmentIds, reason } }), data => decode(data, runRequestedSchema, value => value)),
  decide: (id: string, body: S["DecisionCreate"]) => command(["decide", id, body], key => http.POST("/api/v1/packages/{package_id}/decisions", { params: { path: { package_id: id }, header: { "Idempotency-Key": key } }, body }), data => decode(data, c.decisionSchema, a.decision)),
  drafts: (signal?: AbortSignal) => allPages(async offset => page(await receive(http.GET("/api/v1/admin/program-drafts", { params: { query: { offset, limit: 100 } }, signal })), draftSummarySchema, value => value)),
  draft: async (id: string, signal?: AbortSignal): Promise<c.ProgramDraft> => decode(await receive(http.GET("/api/v1/admin/program-drafts/{draft_id}", { params: { path: { draft_id: id } }, signal })), a.draftSchema, value => value),
  createDraft: (name: string, versionId: string): Promise<c.ProgramDraft> => command(["createDraft", name, versionId], () => http.POST("/api/v1/admin/program-drafts", { body: { name, base_version_id: versionId } }), data => decode(data, a.draftSchema, value => value)),
  saveDraft: (draft: c.ProgramDraft): Promise<c.ProgramDraft> => command(["saveDraft", draft.id, draft.revision, draft.definition], () => http.PATCH("/api/v1/admin/program-drafts/{draft_id}", { params: { path: { draft_id: draft.id } }, body: { expected_revision: draft.revision, definition: draft.definition } }), data => decode(data, a.draftSchema, value => value)),
  validateDraft: (draft: c.ProgramDraft) => command(["validateDraft", draft.id, draft.revision], () => http.POST("/api/v1/admin/program-drafts/{draft_id}/validate", { params: { path: { draft_id: draft.id } }, body: { expected_revision: draft.revision } }), data => decode(data, z.object({ valid: z.boolean(), revision: z.number(), issues: z.array(c.issueSchema) }), value => ({ ...value, issues: (value.issues ?? []).map(a.issue) }))),
  publishDraft: (draft: c.ProgramDraft) => command(["publishDraft", draft.id, draft.revision], key => http.POST("/api/v1/admin/program-drafts/{draft_id}/publish", { params: { path: { draft_id: draft.id }, header: { "Idempotency-Key": key } }, body: { expected_revision: draft.revision } }), data => ({ ...decode(data, versionSchema, value => value), label: `Редакция ${data.version}` })),
  audit: (id: string, signal?: AbortSignal) => allPages(async offset => page(await receive(http.GET("/api/v1/packages/{package_id}/audit", { params: { path: { package_id: id }, query: { offset, limit: 100 } }, signal })), c.auditSchema.shape.items.element, event => ({ ...event, actor: event.actor?.display_name ?? "Система", message: event.action }))),
  sheet: async (id: string, sheet: string, offset = 0, signal?: AbortSignal) => decode(await receive(http.GET("/api/v1/files/{file_id}/sheets/{sheet}", { params: { path: { file_id: id, sheet }, query: { offset, limit: 200 } }, signal })), c.sheetSchema, data => ({ ...data, cells: data.cells.map(cell => ({ ...cell, value: cell.value == null ? null : String(cell.value), formula: cell.formula ?? null })) })),
  contentUrl: (id: string) => `/api/v1/files/${encodeURIComponent(id)}/content`,
  previewUrl: (id: string, page = 1) => `/api/v1/files/${encodeURIComponent(id)}/preview?page=${page}`,
};
