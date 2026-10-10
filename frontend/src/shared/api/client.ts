import createClient from "openapi-fetch";
import type { components, paths } from "./schema.js";

type ErrorEnvelope = components["schemas"]["ApiError"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorEnvelope["details"];
  readonly correlationId: string;

  constructor(status: number, body: ErrorEnvelope) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.correlationId = body.correlation_id;
  }
}

export class MissingCsrfTokenError extends Error {
  constructor() {
    super("Сессия недоступна. Войдите в систему повторно.");
    this.name = "MissingCsrfTokenError";
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return typeof body.code === "string" && typeof body.message === "string"
    && typeof body.correlation_id === "string"
    && typeof body.details === "object" && body.details !== null && !Array.isArray(body.details);
}

export interface ApiClientOptions {
  baseUrl?: string;
  getCsrfToken: () => string | undefined;
  fetch?: typeof globalThis.fetch;
}

export function createApiClient(options: ApiClientOptions) {
  const http = createClient<paths>({
    baseUrl: options.baseUrl ?? "",
    credentials: "same-origin",
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  http.use({
    onRequest({ request, schemaPath }) {
      const changesData = ["POST", "PATCH", "DELETE"].includes(request.method);
      const isLogin = request.method === "POST" && schemaPath === "/api/v1/sessions";
      if (changesData && !isLogin) {
        const token = options.getCsrfToken();
        if (!token) throw new MissingCsrfTokenError();
        request.headers.set("X-CSRF-Token", token);
      }
      return request;
    },
    async onResponse({ response }) {
      if (response.ok) return response;
      const parsed: unknown = await response.clone().json().catch(() => undefined);
      const body: ErrorEnvelope = isErrorEnvelope(parsed) ? parsed : {
        code: "http_error",
        message: "Сервер не смог выполнить запрос.",
        details: {},
        correlation_id: response.headers.get("X-Correlation-ID") ?? crypto.randomUUID(),
      };
      throw new ApiError(response.status, body);
    },
  });

  return {
    http,
    uploadFiles(packageId: string, files: readonly Blob[], expectedRevision: number, key: string) {
      return http.POST("/api/v1/packages/{package_id}/files", {
        params: { path: { package_id: packageId }, header: { "Idempotency-Key": key } },
        body: { files: [...files], expected_revision: expectedRevision },
        bodySerializer(body) {
          const form = new FormData();
          for (const file of body.files) form.append("files", file);
          form.append("expected_revision", String(body.expected_revision));
          return form;
        },
      });
    },
    downloadFile(fileId: string) {
      return http.GET("/api/v1/files/{file_id}/content", {
        params: { path: { file_id: fileId } }, parseAs: "blob",
      });
    },
    getFilePreview(fileId: string, page = 1) {
      return http.GET("/api/v1/files/{file_id}/preview", {
        params: { path: { file_id: fileId }, query: { page } }, parseAs: "blob",
      });
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
