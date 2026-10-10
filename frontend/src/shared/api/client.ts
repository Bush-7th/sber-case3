import { z } from "zod";
import * as c from "./contracts";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public correlationId?: string,
  ) {
    super(code);
  }
}
let csrf: string | undefined;
const pendingKeys = new Map<string, string>();
export function setSession(session: c.Session | null) {
  csrf = session?.csrf_token;
  if (!session) pendingKeys.clear();
}
const prefix = "/api/v1";
const segment = encodeURIComponent;

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method || "GET";
  const headers = new Headers(options.headers);
  let commandFingerprint: string | undefined;
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (method !== "GET") {
    if (csrf) headers.set("X-CSRF-Token", csrf);
    if (!headers.has("Idempotency-Key")) {
      // Keep only a digest, never the request contents (including login credentials).
      const digest = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(`${method}:${path}:${options.body ?? ""}`),
      );
      commandFingerprint = Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
      const key = pendingKeys.get(commandFingerprint) ?? crypto.randomUUID();
      pendingKeys.set(commandFingerprint, key);
      headers.set("Idempotency-Key", key);
    }
  }
  let response: Response;
  try {
    response = await fetch(prefix + path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(0, "NETWORK_ERROR");
  }
  if (!response.ok) {
    // Keep keys after ambiguous server failures; known rejections can be corrected and retried.
    if (response.status < 500 && commandFingerprint)
      pendingKeys.delete(commandFingerprint);
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      typeof error.code === "string" ? error.code : "HTTP_ERROR",
      error.correlation_id,
    );
  }
  if (response.status === 204) {
    if (commandFingerprint) pendingKeys.delete(commandFingerprint);
    return schema.parse(null);
  }
  const body: unknown = await response.json().catch(() => {
    throw new ApiError(response.status, "INVALID_RESPONSE");
  });
  const result = schema.safeParse(body);
  if (!result.success) throw new ApiError(response.status, "CONTRACT_MISMATCH");
  if (commandFingerprint) pendingKeys.delete(commandFingerprint);
  return result.data;
}
const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
// INF01 names users and roles differently from the internal UI model.
const loginResponseSchema = z.object({
  user: z.object({
    id: z.string(),
    display_name: z.string(),
    role: z.enum(["specialist", "administrator"]),
  }),
  expires_at: z.string(),
  csrf_token: z.string().min(1),
}).transform((session): c.Session => ({
  user: {
    id: session.user.id,
    name: session.user.display_name,
    role: session.user.role === "administrator" ? "admin" : "specialist",
  },
  csrf_token: session.csrf_token,
}));
export const api = {
  session: async (signal?: AbortSignal) => {
    try {
      return await request("/sessions", c.sessionSchema, { signal });
    } catch (error) {
      // INF01 has POST/DELETE sessions only. A reload requires a fresh login
      // until the server provides a session recovery endpoint.
      if (error instanceof ApiError && [404, 405].includes(error.status)) {
        return null;
      }
      throw error;
    }
  },
  login: (login: string, password: string) =>
    request("/sessions", loginResponseSchema, json("POST", { username: login, password })),
  logout: () => request("/sessions", z.null(), { method: "DELETE" }),
  programs: (signal?: AbortSignal) =>
    request("/programs", c.pageOf(c.programSchema), { signal }),
  documentTypes: (signal?: AbortSignal) =>
    request("/document-types", c.pageOf(c.documentTypeSchema), { signal }),
  versions: (id: string, signal?: AbortSignal) =>
    request(`/programs/${segment(id)}/versions`, c.pageOf(c.versionSchema), {
      signal,
    }),
  packages: (cursor?: string, signal?: AbortSignal) =>
    request(
      `/packages?limit=25${cursor ? `&cursor=${segment(cursor)}` : ""}`,
      c.pageOf(c.summarySchema),
      { signal },
    ),
  package: (id: string, signal?: AbortSignal) =>
    request(`/packages/${segment(id)}`, c.packageSchema, { signal }),
  createPackage: (body: {
    title: string;
    program_id: string;
    program_version_id: string;
    context: c.ProjectContext;
  }) => request("/packages", c.packageSchema, json("POST", body)),
  configure: (
    id: string,
    body: {
      expected_revision: number;
      program_version_id: string;
      context: c.ProjectContext;
    },
  ) =>
    request(
      `/packages/${segment(id)}/configuration`,
      c.packageSchema,
      json("PATCH", body),
    ),
  upload: (id: string, revision: number, files: File[], key: string) => {
    const body = new FormData();
    body.set("expected_revision", String(revision));
    files.forEach((file) => body.append("files", file));
    return request(`/packages/${segment(id)}/files`, c.uploadSchema, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": key },
    });
  },
  run: (id: string, signal?: AbortSignal) =>
    request(`/verification-runs/${segment(id)}`, c.runSchema, { signal }),
  verify: (id: string, revision: number, retryFile?: string) =>
    request(
      `/packages/${segment(id)}/verification-runs`,
      z.object({ run_id: z.string(), input_revision: z.number() }),
      json("POST", {
        expected_revision: revision,
        ...(retryFile ? { retry_file_version_id: retryFile } : {}),
      }),
    ),
  type: (
    unitId: string,
    revision: number,
    documentType: string,
    reason: string,
  ) =>
    request(
      `/document-units/${segment(unitId)}/type`,
      z.object({ input_revision: z.number(), run_id: z.string() }),
      json("PATCH", {
        expected_revision: revision,
        document_type: documentType,
        reason,
      }),
    ),
  grouping: (unitId: string, revision: number, ids: string[], reason: string) =>
    request(
      `/document-units/${segment(unitId)}/grouping`,
      z.object({ input_revision: z.number(), run_id: z.string() }),
      json("PATCH", {
        expected_revision: revision,
        file_version_ids: ids,
        reason,
      }),
    ),
  decide: (
    id: string,
    body: {
      expected_revision: number;
      action: "accepted" | "needs_revision" | "rejected";
      reason: string;
      report_id: string | null;
    },
  ) =>
    request(
      `/packages/${segment(id)}/decisions`,
      c.decisionSchema,
      json("POST", body),
    ),
  drafts: (signal?: AbortSignal) =>
    request("/admin/program-drafts", c.pageOf(c.draftSchema), { signal }),
  draft: (id: string, signal?: AbortSignal) =>
    request(`/admin/program-drafts/${segment(id)}`, c.draftSchema, { signal }),
  createDraft: (programId: string, versionId: string) =>
    request(
      "/admin/program-drafts",
      c.draftSchema,
      json("POST", { program_id: programId, source_version_id: versionId }),
    ),
  saveDraft: (draft: c.ProgramDraft) =>
    request(
      `/admin/program-drafts/${segment(draft.id)}`,
      c.draftSchema,
      json("PATCH", {
        expected_row_version: draft.row_version,
        name: draft.name,
        requirements: draft.requirements,
        rules: draft.rules,
      }),
    ),
  validateDraft: (draft: c.ProgramDraft) =>
    request(
      `/admin/program-drafts/${segment(draft.id)}/validate`,
      z.object({ valid: z.boolean(), issues: z.array(c.issueSchema) }),
      json("POST", { expected_row_version: draft.row_version }),
    ),
  publishDraft: (draft: c.ProgramDraft) =>
    request(
      `/admin/program-drafts/${segment(draft.id)}/publish`,
      c.versionSchema,
      json("POST", { expected_row_version: draft.row_version }),
    ),
  audit: (id: string, signal?: AbortSignal) =>
    request(`/packages/${segment(id)}/audit`, c.auditSchema, { signal }),
  sheet: (fileId: string, sheet: string, signal?: AbortSignal) =>
    request(
      `/files/${segment(fileId)}/sheets/${segment(sheet)}`,
      c.sheetSchema,
      { signal },
    ),
  contentUrl: (fileId: string) => `${prefix}/files/${segment(fileId)}/content`,
  previewUrl: (fileId: string, page?: number) =>
    `${prefix}/files/${segment(fileId)}/preview${page ? `?page=${page}` : ""}`,
};
