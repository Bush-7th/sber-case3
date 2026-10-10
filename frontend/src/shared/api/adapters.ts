import { z } from "zod";
import type { components } from "./schema";
import * as c from "./contracts";
type S = components["schemas"];

// View models are local to React. Only CON01 DTOs cross the HTTP boundary.
export function evidence(ref: S["EvidenceRef"]): c.Evidence {
  const l = ref.location;
  return { file_id: l.file_id, file_version_id: l.file_version_id,
    page: l.kind === "page" ? l.page : null, sheet: l.kind === "sheet" ? l.sheet : null,
    cell_range: l.kind === "sheet" ? l.cell_range : null,
    paragraph: l.kind === "paragraph" ? l.path : null,
    quote: ref.excerpt, method: ref.extraction_method,
    derived: l.kind === "page" && !!l.preview_id };
}
export function issue(i: S["Issue"]): c.Issue {
  return { code: i.code, severity: i.severity, message: i.message, sources: (i.sources ?? []).map(evidence) };
}
export function file(f: S["FileSummary"], check?: S["FileCheck"]): c.FileCheck {
  return { id: f.id, file_version_id: f.file_version_id, name: f.original_name,
    format: f.format, size_bytes: f.size_bytes, page_count: f.page_count ?? null,
    sheet_names: f.sheet_names ?? [], processing: check?.processing ?? "accepted",
    processing_stage: check?.processing_stage ?? null, verdict: check?.verdict ?? null,
    error: check?.error ? { code: check.error.code, correlation_id: check.error.correlation_id,
      retryable: false } : null };
}
export function decision(d: S["ApplicationDecision"]): z.infer<typeof c.decisionSchema> {
  return { id: d.id, action: d.action, reason: d.reason, author: d.author.display_name,
    created_at: d.decided_at, input_revision: d.input_revision, report_id: d.report_id, freshness: d.freshness };
}
export function summary(p: S["PackageSummary"]): c.PackageSummary {
  return { id: p.id, title: p.title, program_id: p.program_id,
    program_version_id: p.program_version_id, input_revision: p.input_revision,
    updated_at: p.updated_at, file_count: null, verdict: p.verdict, decision: null,
    decision_status: p.decision_status, decision_freshness: p.decision_freshness,
    report_freshness: p.report_freshness, report_provisional: p.report_provisional };
}
const condition = (v: boolean | null | undefined) => v == null ? "unknown" : v ? "true" : "false";
export function contextToWire(context: c.ProjectContext): S["ProjectContext"] {
  const value = (v: string) => v === "unknown" ? null : v === "true";
  return { project_type: context.project_type.trim() || null,
    conditions: { ...context.conditions, certificate_required: value(context.certificate_required),
      gims_required: value(context.gims_required) } };
}
export function packageDetail(p: S["PackageDetail"]): c.Package {
  return { ...summary(p), file_count: p.files?.length ?? 0,
    decision: p.decision ? decision(p.decision) : null,
    context: { project_type: p.project_context.project_type ?? "",
      certificate_required: condition(p.project_context.conditions?.certificate_required),
      gims_required: condition(p.project_context.conditions?.gims_required),
      conditions: p.project_context.conditions ?? {} },
    files: (p.files ?? []).map(f => file(f)), requested_run_id: p.current_run_id,
    decisions: p.decision ? [decision(p.decision)] : [] };
}
function fieldValue(f: S["FieldObservation"]): string | null {
  if (f.normalized == null) return null;
  if (typeof f.normalized === "boolean") return f.normalized ? "Да" : "Нет";
  if (Array.isArray(f.normalized)) return f.normalized.map(i => `${i.description}: ${i.amount ?? "Не найдено"}${i.unit ? ` ${i.unit}` : ""}`).join("; ");
  return f.normalized;
}
export function unit(d: S["DocumentUnit"]): c.DocumentUnit {
  return { id: d.id, predicted_type: d.predicted_type === "unknown" ? null : d.predicted_type,
    effective_type: d.effective_type === "unknown" ? null : d.effective_type,
    type_overridden: d.type_overridden,
    file_version_ids: [...new Set(d.fragments.map(f => f.location.file_version_id))],
    fragments: d.fragments.map(f => ({ id: f.id, source: evidence({ location: f.location, excerpt: "", extraction_method: "native" }) })),
    fields: (d.fields ?? []).map(f => ({ key: f.field_id, label: f.field_id,
      value: fieldValue(f), known_state: f.known_state === "unreadable" ? "unknown" : f.known_state,
      sources: (f.evidence ?? []).map(evidence) })), issues: (d.issues ?? []).map(issue) };
}
export function run(r: S["VerificationRun"]): c.Run {
  return { id: r.id, input_revision: r.input_revision, progress_version: r.progress_version,
    status: r.status, coverage: r.coverage,
    freshness: r.freshness === "outdated" || r.report?.freshness === "outdated" ||
      (r.report && (r.report.input_revision !== r.input_revision || r.report.run_id !== r.id)) ? "outdated" : "current",
    provisional: r.report?.provisional ?? r.coverage !== "complete",
    progress: { accepted: r.progress.total, running: r.progress.determining,
      terminal: r.progress.checked + r.progress.processing_error },
    files: (r.files ?? []).map(f => file(f.file, f)), document_units: (r.documents ?? []).map(unit),
    provider: { provider: r.model_profile.provider, model: r.model_profile.model, invocation_id: null },
    report: r.report ? { id: r.report.id, basis: r.report.basis, verdict: r.report.verdict,
      issues: (r.report.issues ?? []).map(issue), requirements: (r.report.requirements ?? []).map(q => ({
        document_type: q.document_type, kind: q.kind, status: q.status, severity: q.severity, message: q.message })),
      rules: (r.report.rules ?? []).map(rule => ({ id: rule.rule_id, name: rule.rule_id,
        status: rule.status, explanation: rule.message, sources: (rule.sources ?? []).map(evidence) })) } : null };
}

// Admin edits preserve the complete definition, including recursive predicates,
// field schemas, operand names and clarification flags.
const documentType = z.enum(["application", "consent", "certificate", "presentation", "cost_justification", "bank_statement", "property_document", "guarantee_letter", "gims_declaration"]);
export const predicateSchema: z.ZodType<NonNullable<S["ProgramDraft"]["definition"]["requirements"][number]["predicate"]>> = z.lazy(() => z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("equals"), field: z.string().min(1), value: z.union([z.string(), z.boolean()]) }),
  z.object({ kind: z.literal("is_true"), field: z.string().min(1) }),
  z.object({ kind: z.literal("all"), operands: z.array(predicateSchema).min(1) }),
  z.object({ kind: z.literal("any"), operands: z.array(predicateSchema).min(1) }),
]));
const severity = z.enum(["error", "warning", "info"]);
const rule = z.object({ id: z.string().min(1), family: z.enum(["required_fields", "non_empty", "matches_regex", "date_compare", "ratio_gte", "amount_equal", "same_subject_value"]),
  bindings: z.array(z.object({ operand: z.string().min(1), document_type: documentType,
    field_id: z.string().min(1), subject_role: z.enum(["applicant", "guarantor", "person", "unknown"]) })).default([]),
  parameters: z.object({ factor: z.string().regex(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/).nullable().optional(),
    pattern: z.string().nullable().optional(), date_mode: z.enum(["not_future", "not_expired"]).nullable().optional(),
    field_ids: z.array(z.string()).default([]) }).default({ field_ids: [] }),
  severity, needs_clarification: z.boolean().default(false) });
export const definitionSchema = z.object({ name: z.string().min(1), description: z.string(),
  document_types: z.array(z.object({ id: documentType, label: z.string(), description: z.string(),
    fields: z.array(z.object({ id: z.string(), label: z.string(), data_type: z.enum(["text", "decimal", "money", "date", "boolean", "expense_items"]), unit: z.string().nullable().optional() })),
    minimum_field_ids: z.array(z.string()), extension: z.boolean().default(false) })),
  requirements: z.array(z.object({ id: z.string().min(1), document_type: documentType,
    kind: z.enum(["required", "conditional", "optional"]), quantity: z.number().int().positive(),
    predicate: predicateSchema.nullable().optional(), missing_severity: severity,
    needs_clarification: z.boolean().default(false) })), rules: z.array(rule) });
export const draftSchema = z.object({ id: z.string(), program_id: z.string().nullable(),
  name: z.string(), revision: z.number().int().nonnegative(), status: z.enum(["draft", "published"]),
  updated_at: z.string(), base_version_id: z.string().nullable(), definition: definitionSchema });
