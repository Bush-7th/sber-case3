import { z } from "zod";
import type { components } from "./schema";

// Local screen models. HTTP requests/responses use the generated CON01 types.

export const roleSchema = z.enum(["specialist", "admin"]);
export const sessionSchema = z.object({
  user: z.object({ id: z.string(), name: z.string(), role: roleSchema }),
  csrf_token: z.string().min(1),
});
export type Session = z.infer<typeof sessionSchema>;
export const severitySchema = z.enum(["error", "warning", "attention", "info"]);
export const verdictSchema = z.enum(["pass", "review_required", "issues"]);
export const sourceSchema = z.object({
  file_id: z.string(),
  file_version_id: z.string(),
  page: z.number().int().positive().nullable(),
  sheet: z.string().nullable(),
  cell_range: z.string().nullable(),
  paragraph: z.string().nullable(),
  quote: z.string().nullable(),
  method: z.enum(["native", "ocr", "vision"]),
  derived: z.boolean(),
});
export type Evidence = z.infer<typeof sourceSchema>;
export const issueSchema = z.object({
  code: z.string(),
  severity: severitySchema,
  message: z.string(),
  sources: z.array(sourceSchema),
});
export type Issue = z.infer<typeof issueSchema>;
export const fieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.string().nullable(),
  known_state: z.enum(["known", "missing", "unknown", "conflict"]),
  sources: z.array(sourceSchema),
});
export const unitSchema = z.object({
  id: z.string(),
  predicted_type: z.string().nullable(),
  effective_type: z.string().nullable(),
  type_overridden: z.boolean(),
  fragments: z.array(z.object({ id: z.string(), source: sourceSchema })),
  file_version_ids: z.array(z.string()),
  fields: z.array(fieldSchema),
  issues: z.array(issueSchema),
});
export type DocumentUnit = z.infer<typeof unitSchema>;
export const fileSchema = z.object({
  id: z.string(),
  file_version_id: z.string(),
  page_count: z.number().int().positive().nullable(),
  sheet_names: z.array(z.string()),
  name: z.string(),
  format: z.string(),
  size_bytes: z.number(),
  processing: z.enum([
    "accepted",
    "determining",
    "checked",
    "processing_error",
  ]),
  processing_stage: z
    .enum(["preparing", "ocr", "extracting", "validating"])
    .nullable(),
  verdict: verdictSchema.nullable(),
  error: z
    .object({
      code: z.string(),
      retryable: z.boolean(),
      correlation_id: z.string().nullable(),
    })
    .nullable(),
});
export type FileCheck = z.infer<typeof fileSchema>;
export const decisionSchema = z.object({
  id: z.string(),
  action: z.enum(["accepted", "needs_revision", "rejected"]),
  reason: z.string(),
  author: z.string(),
  created_at: z.string(),
  input_revision: z.number(),
  report_id: z.string().nullable(),
  freshness: z.enum(["current", "outdated"]),
});
export const contextSchema = z.object({
  project_type: z.string(),
  certificate_required: z.enum(["true", "false", "unknown"]),
  gims_required: z.enum(["true", "false", "unknown"]),
  conditions: z.record(z.string(), z.boolean().nullable()),
});
export type ProjectContext = z.infer<typeof contextSchema>;
export const summarySchema = z.object({
  id: z.string(),
  title: z.string(),
  program_id: z.string(),
  program_version_id: z.string(),
  input_revision: z.number(),
  updated_at: z.string(),
  file_count: z.number().nullable(),
  verdict: verdictSchema.nullable(),
  decision: decisionSchema.nullable(),
  decision_status: z.enum(["accepted", "needs_revision", "rejected", "not_decided"]),
  decision_freshness: z.enum(["current", "outdated"]).nullable(),
  report_freshness: z.enum(["current", "outdated"]).nullable(),
  report_provisional: z.boolean().nullable(),
});
export type PackageSummary = z.infer<typeof summarySchema>;
export const packageSchema = summarySchema.extend({
  context: contextSchema,
  files: z.array(fileSchema),
  requested_run_id: z.string().nullable(),
  decisions: z.array(decisionSchema),
});
export type Package = z.infer<typeof packageSchema>;
export const runSchema = z.object({
  id: z.string(),
  input_revision: z.number(),
  progress_version: z.number(),
  status: z.enum(["queued", "running", "completed", "failed", "cancelled"]),
  coverage: z.enum(["partial", "complete"]),
  freshness: z.enum(["current", "outdated"]),
  provisional: z.boolean(),
  progress: z.object({
    accepted: z.number(),
    running: z.number(),
    terminal: z.number(),
  }),
  files: z.array(fileSchema),
  document_units: z.array(unitSchema),
  report: z
    .object({
      id: z.string(),
      basis: z.literal("machine"),
      verdict: verdictSchema,
      issues: z.array(issueSchema),
      requirements: z.array(
        z.object({
          document_type: z.string(),
          kind: z.enum(["required", "conditional", "optional"]),
          severity: severitySchema,
          status: z.enum([
            "found",
            "missing",
            "pending",
            "unknown",
            "not_applicable",
          ]),
          message: z.string(),
        }),
      ),
      rules: z.array(
        z.object({
          id: z.string(),
          name: z.string(),
          status: z.enum(["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]),
          explanation: z.string(),
          sources: z.array(sourceSchema),
        }),
      ),
    })
    .nullable(),
  provider: z
    .object({
      provider: z.string(),
      model: z.string(),
      invocation_id: z.string().nullable(),
    })
    .nullable(),
});
export type Run = z.infer<typeof runSchema>;
export const programSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
});
export type Program = z.infer<typeof programSchema>;
export type RuleDefinition = components["schemas"]["RuleDefinition"];
export type ProgramDraft = components["schemas"]["ProgramDraft"];
export const uploadSchema = z.object({
  input_revision: z.number(),
  run_id: z.string().nullable(),
  accepted: z.array(
    z.object({ file_version_id: z.string(), name: z.string() }),
  ),
  rejected: z.array(z.object({ name: z.string(), code: z.string() })),
});
export const sheetSchema = z.object({
  sheet: z.string(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  cells: z.array(
    z.object({
      address: z.string(),
      value: z.string().nullable(),
      formula: z.string().nullable(),
      known_state: z.enum(["known", "missing", "unreadable"]),
    }),
  ),
});
export const auditSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      action: z.string(),
      actor: z.string(),
      created_at: z.string(),
      input_revision: z.number().nullable(),
      run_id: z.string().nullable(),
      message: z.string(),
    }),
  ),
});
