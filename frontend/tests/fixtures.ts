import type { components } from "../src/shared/api/schema";
type S = components["schemas"];
export const ids = {
  user: "11111111-1111-4111-8111-111111111111", program: "22222222-2222-4222-8222-222222222222",
  version: "33333333-3333-4333-8333-333333333333", package: "44444444-4444-4444-8444-444444444444",
  file: "55555555-5555-4555-8555-555555555555", fileVersion: "66666666-6666-4666-8666-666666666666",
  run: "77777777-7777-4777-8777-777777777777", report: "88888888-8888-4888-8888-888888888888",
  draft: "99999999-9999-4999-8999-999999999999", document: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  fragment: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", correlation: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
};
export const timestamp = "2026-10-10T10:00:00Z";
export const session: S["SessionResponse"] = { user: { id: ids.user, display_name: "Тестовый специалист", role: "specialist" }, csrf_token: "test-csrf", expires_at: "2026-10-10T20:00:00Z" };
export const program: S["ProgramSummary"] = { id: ids.program, name: "Программа инноваций", latest_version_id: ids.version };
export const definition: S["ProgramDraft"]["definition"] = {
  name: program.name, description: "Контрактная фикстура", document_types: [{ id: "application", label: "Заявление", description: "Заявление", extension: false,
    fields: [{ id: "own_funds", label: "Собственные средства", data_type: "money", unit: "RUB" }], minimum_field_ids: ["own_funds"] }],
  requirements: [{ id: "application_required", document_type: "application", kind: "required", quantity: 1, predicate: null, missing_severity: "error", needs_clarification: false },
    { id: "conditional_certificate", document_type: "certificate", kind: "conditional", quantity: 1, missing_severity: "warning", needs_clarification: false,
      predicate: { kind: "all", operands: [{ kind: "is_true", field: "certificate_required" }, { kind: "equals", field: "project_type", value: "Исследование" }] } }],
  rules: [{ id: "ratio", family: "ratio_gte", bindings: [{ operand: "own_funds", document_type: "application", field_id: "own_funds", subject_role: "applicant" }], parameters: { factor: "0.50", field_ids: [] }, severity: "error", needs_clarification: false }],
};
export const version: S["ProgramVersion"] = { id: ids.version, program_id: ids.program, version: 1, published_at: timestamp, definition };
export const draft: S["ProgramDraft"] = { id: ids.draft, program_id: ids.program, base_version_id: ids.version, name: program.name, revision: 1, status: "draft", updated_at: timestamp, definition };
export const file: S["FileSummary"] = { id: ids.file, file_version_id: ids.fileVersion, original_name: "исходный.pdf", format: "pdf", size_bytes: 200, sha256: "a".repeat(64), created_at: timestamp, page_count: 2, sheet_names: [] };
export const item: S["PackageDetail"] = {
  id: ids.package, title: "Заявка на инновационный проект", program_id: ids.program, program_version_id: ids.version,
  input_revision: 2, created_at: timestamp, updated_at: timestamp, current_run_id: ids.run,
  verdict: "review_required", report_freshness: "current", report_provisional: true,
  decision_status: "not_decided", decision_freshness: null, project_context: { project_type: null, conditions: { certificate_required: null, gims_required: null, another_condition: false } },
  files: [file], report: null, decision: null,
};
export const evidence: S["EvidenceRef"] = { location: { kind: "page", file_id: ids.file, file_version_id: ids.fileVersion, page: 2, preview_id: null, bbox: null }, excerpt: "Фрагмент источника", extraction_method: "vision", ocr_result_id: null };
export const document: S["DocumentUnit"] = { id: ids.document, version_id: ids.version, predicted_type: "application", effective_type: "application", type_overridden: false,
  fragments: [{ id: ids.fragment, location: evidence.location }],
  fields: [{ field_id: "own_funds", data_type: "money", raw: null, normalized: null, known_state: "missing", subject_role: "applicant", source: "machine", unit: "RUB", evidence: [] }], issues: [] };
export const run: S["VerificationRun"] = {
  id: ids.run, package_id: ids.package, input_revision: 2, progress_version: 1, status: "completed", coverage: "partial", freshness: "current",
  reference_date: "2026-10-10", timezone: "Europe/Moscow", model_profile: { provider: "external", model: "test-model", prompt_version: "1", preparation_version: "1", ocr_profile: null },
  progress: { total: 1, accepted: 0, determining: 0, checked: 1, processing_error: 0 },
  files: [{ file, processing: "checked", processing_stage: null, predicted_type: "application", verdict: "review_required", issues: [], document_unit_ids: [ids.document], invocations: [], error: null }], documents: [document], error: null,
  report: { id: ids.report, package_id: ids.package, run_id: ids.run, input_revision: 2, progress_version: 1, program_version_id: ids.version, basis: "machine", created_at: timestamp, reference_date: "2026-10-10", timezone: "Europe/Moscow", coverage: "partial", provisional: true, freshness: "current", verdict: "review_required", issues: [],
    requirements: [{ requirement_id: "certificate", document_type: "certificate", kind: "conditional", status: "missing", severity: "warning", message: "Сертификат не найден", document_unit_ids: [] },
      { requirement_id: "optional", document_type: "presentation", kind: "optional", status: "missing", severity: "info", message: "Дополнительная презентация отсутствует", document_unit_ids: [] }],
    rules: [{ rule_id: "amount", status: "UNKNOWN", severity: "warning", message: "Запрашиваемая сумма не найдена в обосновании.", operands: {}, formula: null, sources: [evidence] }],
  },
};
export function pageOf<T>(items: T[], offset = 0, total = items.length) { return { items, total, offset, limit: 25 }; }
export function errorBody(code: string, details = {}) { return { code, message: "Ошибка контрактного теста", details, correlation_id: ids.correlation }; }
export const requested = { package_id: ids.package, input_revision: 3, run_id: ids.run, correlation_id: ids.correlation } satisfies S["RunRequested"];
