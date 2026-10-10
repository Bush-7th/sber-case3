// Generated from backend/openapi.json. Run npm run api:generate.
export interface paths {
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness */
        get: operations["liveness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness Endpoint */
        get: operations["readiness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session"];
        put?: never;
        /** Create Session */
        post: operations["create_session"];
        /** Delete Session */
        delete: operations["delete_session"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/programs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Programs */
        get: operations["list_programs"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/programs/{program_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Program Versions */
        get: operations["list_program_versions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/packages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Packages */
        get: operations["list_packages"];
        put?: never;
        /** Create Package */
        post: operations["create_package"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/packages/{package_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Package */
        get: operations["get_package"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/packages/{package_id}/files": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Files */
        post: operations["upload_files"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/packages/{package_id}/configuration": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Configuration */
        patch: operations["update_configuration"];
        trace?: never;
    };
    "/api/v1/packages/{package_id}/verification-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Verification Run */
        post: operations["create_verification_run"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/verification-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Verification Run */
        get: operations["get_verification_run"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/files/{file_id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download File */
        get: operations["download_file"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/files/{file_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get File Preview */
        get: operations["get_file_preview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/files/{file_id}/sheets/{sheet}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Sheet */
        get: operations["get_sheet"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/document-units/{document_id}/type": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Document Type */
        patch: operations["update_document_type"];
        trace?: never;
    };
    "/api/v1/document-units/{document_id}/grouping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Document Grouping */
        patch: operations["update_document_grouping"];
        trace?: never;
    };
    "/api/v1/packages/{package_id}/decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Decision */
        post: operations["create_decision"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/program-drafts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Program Drafts */
        get: operations["list_program_drafts"];
        put?: never;
        /** Create Program Draft */
        post: operations["create_program_draft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/program-drafts/{draft_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Program Draft */
        get: operations["get_program_draft"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Program Draft */
        patch: operations["update_program_draft"];
        trace?: never;
    };
    "/api/v1/admin/program-drafts/{draft_id}/rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Rule */
        patch: operations["update_rule"];
        trace?: never;
    };
    "/api/v1/admin/program-drafts/{draft_id}/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Validate Program Draft */
        post: operations["validate_program_draft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/program-drafts/{draft_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Program Draft */
        post: operations["publish_program_draft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/packages/{package_id}/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Audit */
        get: operations["list_audit"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AllPredicate */
        "AllPredicate-Input": {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "all";
            /** Operands */
            operands: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Input"] | components["schemas"]["AnyPredicate-Input"])[];
        };
        /** AllPredicate */
        "AllPredicate-Output": {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "all";
            /** Operands */
            operands: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Output"] | components["schemas"]["AnyPredicate-Output"])[];
        };
        /** AnyPredicate */
        "AnyPredicate-Input": {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "any";
            /** Operands */
            operands: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Input"] | components["schemas"]["AnyPredicate-Input"])[];
        };
        /** AnyPredicate */
        "AnyPredicate-Output": {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "any";
            /** Operands */
            operands: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Output"] | components["schemas"]["AnyPredicate-Output"])[];
        };
        /** ApiError */
        ApiError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Details */
            details?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
        };
        /** ApplicationDecision */
        ApplicationDecision: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Package Id
             * Format: uuid
             */
            package_id: string;
            /** Input Revision */
            input_revision: number;
            /** Report Id */
            report_id: string | null;
            action: components["schemas"]["DecisionAction"];
            /** Reason */
            reason: string;
            author: components["schemas"]["UserSummary"];
            /**
             * Decided At
             * Format: date-time
             */
            decided_at: string;
            freshness: components["schemas"]["Freshness"];
        };
        /** AuditEvent */
        AuditEvent: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            actor: components["schemas"]["UserSummary"] | null;
            /** Action */
            action: string;
            resource: components["schemas"]["ResourceRef"];
            /** Input Revision */
            input_revision: number | null;
            /** Run Id */
            run_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
            /** Details */
            details?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** Body_upload_files */
        Body_upload_files: {
            /** Files */
            files: Blob[];
            /** Expected Revision */
            expected_revision: number;
        };
        /**
         * BoundingBox
         * @description Coordinates relative to the indicated source/preview page, within [0, 1].
         */
        BoundingBox: {
            /** X */
            x: number;
            /** Y */
            y: number;
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /** ConfigurationUpdate */
        ConfigurationUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Program Version Id */
            program_version_id?: string | null;
            project_context?: components["schemas"]["ProjectContext"] | null;
        };
        /**
         * Coverage
         * @enum {string}
         */
        Coverage: "partial" | "complete";
        /**
         * DecisionAction
         * @enum {string}
         */
        DecisionAction: "accepted" | "needs_revision" | "rejected";
        /** DecisionCreate */
        DecisionCreate: {
            /** Expected Revision */
            expected_revision: number;
            action: components["schemas"]["DecisionAction"];
            /** Reason */
            reason: string;
            /** Report Id */
            report_id?: string | null;
        };
        /**
         * DocumentType
         * @enum {string}
         */
        DocumentType: "application" | "consent" | "certificate" | "presentation" | "cost_justification" | "bank_statement" | "property_document" | "guarantee_letter" | "gims_declaration";
        /** DocumentTypeDefinition */
        DocumentTypeDefinition: {
            id: components["schemas"]["DocumentType"];
            /** Label */
            label: string;
            /** Description */
            description: string;
            /** Fields */
            fields: components["schemas"]["FieldDefinition"][];
            /** Minimum Field Ids */
            minimum_field_ids: string[];
            /**
             * Extension
             * @default false
             */
            extension: boolean;
        };
        /** DocumentUnit */
        DocumentUnit: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Version Id
             * Format: uuid
             */
            version_id: string;
            /** Predicted Type */
            predicted_type: components["schemas"]["DocumentType"] | "unknown";
            /** Effective Type */
            effective_type: components["schemas"]["DocumentType"] | "unknown";
            /** Type Overridden */
            type_overridden: boolean;
            /** Fragments */
            fragments: components["schemas"]["SourceFragmentRef"][];
            /** Fields */
            fields?: components["schemas"]["FieldObservation"][];
            /** Issues */
            issues?: components["schemas"]["Issue"][];
        };
        /** DraftValidation */
        DraftValidation: {
            /**
             * Draft Id
             * Format: uuid
             */
            draft_id: string;
            /** Revision */
            revision: number;
            /** Valid */
            valid: boolean;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
        };
        /** EqualsPredicate */
        EqualsPredicate: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "equals";
            /** Field */
            field: string;
            /** Value */
            value: string | boolean;
        };
        /** EvidenceRef */
        EvidenceRef: {
            /** Location */
            location: components["schemas"]["PageLocation"] | components["schemas"]["SheetLocation"] | components["schemas"]["ParagraphLocation"];
            /** Excerpt */
            excerpt: string;
            /**
             * Extraction Method
             * @enum {string}
             */
            extraction_method: "native" | "ocr" | "vision";
            /** Ocr Result Id */
            ocr_result_id?: string | null;
        };
        /** ExpenseItem */
        ExpenseItem: {
            /** Description */
            description: string;
            /** Amount */
            amount: string | null;
            /** Unit */
            unit?: string | null;
            /** Evidence */
            evidence?: components["schemas"]["EvidenceRef"][];
        };
        /** FieldBinding */
        FieldBinding: {
            /** Operand */
            operand: string;
            document_type: components["schemas"]["DocumentType"];
            /** Field Id */
            field_id: string;
            /** @default unknown */
            subject_role: components["schemas"]["SubjectRole"];
        };
        /**
         * FieldDataType
         * @enum {string}
         */
        FieldDataType: "text" | "decimal" | "money" | "date" | "boolean" | "expense_items";
        /** FieldDefinition */
        FieldDefinition: {
            /** Id */
            id: string;
            /** Label */
            label: string;
            data_type: components["schemas"]["FieldDataType"];
            /** Unit */
            unit?: string | null;
        };
        /** FieldObservation */
        FieldObservation: {
            /** Field Id */
            field_id: string;
            data_type: components["schemas"]["FieldDataType"];
            /** Raw */
            raw: string | null;
            /** Normalized */
            normalized: string | boolean | components["schemas"]["ExpenseItem"][] | null;
            /**
             * Known State
             * @enum {string}
             */
            known_state: "known" | "missing" | "unreadable" | "conflict";
            /** @default unknown */
            subject_role: components["schemas"]["SubjectRole"];
            /** Unit */
            unit?: string | null;
            /**
             * Source
             * @default machine
             * @constant
             */
            source: "machine";
            /** Evidence */
            evidence?: components["schemas"]["EvidenceRef"][];
        };
        /** FileCheck */
        FileCheck: {
            file: components["schemas"]["FileSummary"];
            processing: components["schemas"]["ProcessingStatus"];
            processing_stage: components["schemas"]["ProcessingStage"] | null;
            /** Predicted Type */
            predicted_type: components["schemas"]["DocumentType"] | "unknown" | null;
            verdict: components["schemas"]["Verdict"] | null;
            /** Issues */
            issues?: components["schemas"]["Issue"][];
            /** Document Unit Ids */
            document_unit_ids?: string[];
            /** Invocations */
            invocations?: components["schemas"]["ProviderMetadata"][];
            error?: components["schemas"]["ApiError"] | null;
        };
        /**
         * FileFormat
         * @enum {string}
         */
        FileFormat: "pdf" | "doc" | "docx" | "xls" | "xlsx" | "jpg" | "png";
        /** FileSummary */
        FileSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * File Version Id
             * Format: uuid
             */
            file_version_id: string;
            /** Original Name */
            original_name: string;
            format: components["schemas"]["FileFormat"];
            /** Size Bytes */
            size_bytes: number;
            /** Sha256 */
            sha256: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Page Count */
            page_count?: number | null;
            /** Sheet Names */
            sheet_names?: string[];
        };
        /**
         * Freshness
         * @enum {string}
         */
        Freshness: "current" | "outdated";
        /** GroupingUpdate */
        GroupingUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Fragment Ids */
            fragment_ids: string[];
            /** Reason */
            reason: string;
        };
        /** IsTruePredicate */
        IsTruePredicate: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "is_true";
            /** Field */
            field: string;
        };
        /** Issue */
        Issue: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            severity: components["schemas"]["Severity"];
            /**
             * Category
             * @enum {string}
             */
            category: "document" | "technical" | "configuration";
            /** Message */
            message: string;
            /** Rule Id */
            rule_id?: string | null;
            /** Objects */
            objects?: components["schemas"]["ResourceRef"][];
            /** Sources */
            sources?: components["schemas"]["EvidenceRef"][];
            next_action?: components["schemas"]["IssueAction"] | null;
        };
        /** IssueAction */
        IssueAction: {
            /**
             * Action
             * @enum {string}
             */
            action: "upload_document" | "open_source" | "correct_type" | "retry_verification" | "clarify_rule" | "add_to_revision_request";
            target?: components["schemas"]["ResourceRef"] | null;
        };
        JsonValue: unknown;
        /** LivenessResponse */
        LivenessResponse: {
            /**
             * Status
             * @default alive
             * @constant
             */
            status: "alive";
        };
        /** MachineReport */
        MachineReport: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Package Id
             * Format: uuid
             */
            package_id: string;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /** Input Revision */
            input_revision: number;
            /** Progress Version */
            progress_version: number;
            /**
             * Program Version Id
             * Format: uuid
             */
            program_version_id: string;
            /**
             * Basis
             * @default machine
             * @constant
             */
            basis: "machine";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Reference Date
             * Format: date
             */
            reference_date: string;
            /** Timezone */
            timezone: string;
            coverage: components["schemas"]["Coverage"];
            /** Provisional */
            provisional: boolean;
            freshness: components["schemas"]["Freshness"];
            verdict: components["schemas"]["Verdict"];
            /** Requirements */
            requirements?: components["schemas"]["RequirementResult"][];
            /** Rules */
            rules?: components["schemas"]["RuleResult"][];
            /** Issues */
            issues?: components["schemas"]["Issue"][];
        };
        /** ModelProfile */
        ModelProfile: {
            /**
             * Provider
             * @enum {string}
             */
            provider: "external" | "local";
            /** Model */
            model: string;
            /** Prompt Version */
            prompt_version: string;
            /** Preparation Version */
            preparation_version: string;
            /** Ocr Profile */
            ocr_profile?: string | null;
        };
        /** PackageCreate */
        PackageCreate: {
            /** Title */
            title: string;
            /**
             * Program Version Id
             * Format: uuid
             */
            program_version_id: string;
            project_context?: components["schemas"]["ProjectContext"];
        };
        /** PackageDetail */
        PackageDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            /**
             * Program Id
             * Format: uuid
             */
            program_id: string;
            /**
             * Program Version Id
             * Format: uuid
             */
            program_version_id: string;
            /** Input Revision */
            input_revision: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Current Run Id */
            current_run_id: string | null;
            verdict: components["schemas"]["Verdict"] | null;
            report_freshness: components["schemas"]["Freshness"] | null;
            /** Report Provisional */
            report_provisional: boolean | null;
            /** Decision Status */
            decision_status: components["schemas"]["DecisionAction"] | "not_decided";
            decision_freshness: components["schemas"]["Freshness"] | null;
            project_context: components["schemas"]["ProjectContext"];
            /** Files */
            files?: components["schemas"]["FileSummary"][];
            report?: components["schemas"]["MachineReport"] | null;
            decision?: components["schemas"]["ApplicationDecision"] | null;
        };
        /** PackageSummary */
        PackageSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            /**
             * Program Id
             * Format: uuid
             */
            program_id: string;
            /**
             * Program Version Id
             * Format: uuid
             */
            program_version_id: string;
            /** Input Revision */
            input_revision: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Current Run Id */
            current_run_id: string | null;
            verdict: components["schemas"]["Verdict"] | null;
            report_freshness: components["schemas"]["Freshness"] | null;
            /** Report Provisional */
            report_provisional: boolean | null;
            /** Decision Status */
            decision_status: components["schemas"]["DecisionAction"] | "not_decided";
            decision_freshness: components["schemas"]["Freshness"] | null;
        };
        /** PageLocation */
        PageLocation: {
            /**
             * File Id
             * Format: uuid
             */
            file_id: string;
            /**
             * File Version Id
             * Format: uuid
             */
            file_version_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "page";
            /** Page */
            page: number;
            /** Preview Id */
            preview_id?: string | null;
            bbox?: components["schemas"]["BoundingBox"] | null;
        };
        /** Page[AuditEvent] */
        Page_AuditEvent_: {
            /** Items */
            items: components["schemas"]["AuditEvent"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** Page[PackageSummary] */
        Page_PackageSummary_: {
            /** Items */
            items: components["schemas"]["PackageSummary"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** Page[ProgramDraftSummary] */
        Page_ProgramDraftSummary_: {
            /** Items */
            items: components["schemas"]["ProgramDraftSummary"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** Page[ProgramSummary] */
        Page_ProgramSummary_: {
            /** Items */
            items: components["schemas"]["ProgramSummary"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** Page[ProgramVersion] */
        Page_ProgramVersion_: {
            /** Items */
            items: components["schemas"]["ProgramVersion"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** ParagraphLocation */
        ParagraphLocation: {
            /**
             * File Id
             * Format: uuid
             */
            file_id: string;
            /**
             * File Version Id
             * Format: uuid
             */
            file_version_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "paragraph";
            /** Path */
            path: string;
        };
        /**
         * ProcessingStage
         * @enum {string}
         */
        ProcessingStage: "preparing" | "ocr" | "extracting" | "validating";
        /**
         * ProcessingStatus
         * @enum {string}
         */
        ProcessingStatus: "accepted" | "determining" | "checked" | "processing_error";
        /** ProgramDefinition */
        "ProgramDefinition-Input": {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Document Types */
            document_types: components["schemas"]["DocumentTypeDefinition"][];
            /** Requirements */
            requirements: components["schemas"]["RequirementDefinition-Input"][];
            /** Rules */
            rules: components["schemas"]["RuleDefinition"][];
        };
        /** ProgramDefinition */
        "ProgramDefinition-Output": {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Document Types */
            document_types: components["schemas"]["DocumentTypeDefinition"][];
            /** Requirements */
            requirements: components["schemas"]["RequirementDefinition-Output"][];
            /** Rules */
            rules: components["schemas"]["RuleDefinition"][];
        };
        /** ProgramDraft */
        ProgramDraft: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Program Id */
            program_id: string | null;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "published";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Base Version Id */
            base_version_id: string | null;
            definition: components["schemas"]["ProgramDefinition-Output"];
        };
        /** ProgramDraftCreate */
        ProgramDraftCreate: {
            /** Name */
            name: string;
            /** Base Version Id */
            base_version_id?: string | null;
        };
        /** ProgramDraftSummary */
        ProgramDraftSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Program Id */
            program_id: string | null;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "published";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ProgramDraftUpdate */
        ProgramDraftUpdate: {
            /** Expected Revision */
            expected_revision: number;
            definition: components["schemas"]["ProgramDefinition-Input"];
        };
        /** ProgramSummary */
        ProgramSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Latest Version Id
             * Format: uuid
             */
            latest_version_id: string;
        };
        /** ProgramVersion */
        ProgramVersion: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Program Id
             * Format: uuid
             */
            program_id: string;
            /** Version */
            version: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            definition: components["schemas"]["ProgramDefinition-Output"];
        };
        /** ProjectContext */
        ProjectContext: {
            /** Project Type */
            project_type?: string | null;
            /** Conditions */
            conditions?: {
                [key: string]: boolean | null;
            };
        };
        /** ProviderMetadata */
        ProviderMetadata: {
            /**
             * Provider
             * @enum {string}
             */
            provider: "external" | "local";
            /** Model */
            model: string;
            /** Prompt Version */
            prompt_version: string;
            /** Schema Hash */
            schema_hash: string;
            /**
             * Invocation Id
             * Format: uuid
             */
            invocation_id: string;
        };
        /** ReadinessResponse */
        ReadinessResponse: {
            /** Api Ready */
            api_ready: boolean;
            /** Pipeline Ready */
            pipeline_ready: boolean;
            /** Checks */
            checks: {
                [key: string]: "ready" | "not_ready" | "not_checked";
            };
        };
        /** RequirementDefinition */
        "RequirementDefinition-Input": {
            /** Id */
            id: string;
            document_type: components["schemas"]["DocumentType"];
            kind: components["schemas"]["RequirementKind"];
            /** Quantity */
            quantity: number;
            /** Predicate */
            predicate?: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Input"] | components["schemas"]["AnyPredicate-Input"]) | null;
            missing_severity: components["schemas"]["Severity"];
            /**
             * Needs Clarification
             * @default false
             */
            needs_clarification: boolean;
        };
        /** RequirementDefinition */
        "RequirementDefinition-Output": {
            /** Id */
            id: string;
            document_type: components["schemas"]["DocumentType"];
            kind: components["schemas"]["RequirementKind"];
            /** Quantity */
            quantity: number;
            /** Predicate */
            predicate?: (components["schemas"]["EqualsPredicate"] | components["schemas"]["IsTruePredicate"] | components["schemas"]["AllPredicate-Output"] | components["schemas"]["AnyPredicate-Output"]) | null;
            missing_severity: components["schemas"]["Severity"];
            /**
             * Needs Clarification
             * @default false
             */
            needs_clarification: boolean;
        };
        /**
         * RequirementKind
         * @enum {string}
         */
        RequirementKind: "required" | "conditional" | "optional";
        /** RequirementResult */
        RequirementResult: {
            /** Requirement Id */
            requirement_id: string;
            document_type: components["schemas"]["DocumentType"];
            kind: components["schemas"]["RequirementKind"];
            /**
             * Status
             * @enum {string}
             */
            status: "found" | "missing" | "pending" | "unknown" | "not_applicable";
            severity: components["schemas"]["Severity"];
            /** Message */
            message: string;
            /** Document Unit Ids */
            document_unit_ids?: string[];
        };
        /** ResourceRef */
        ResourceRef: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "package" | "file" | "document";
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** RevisionCommand */
        RevisionCommand: {
            /** Expected Revision */
            expected_revision: number;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "specialist" | "administrator";
        /** RuleDefinition */
        RuleDefinition: {
            /** Id */
            id: string;
            /**
             * Family
             * @enum {string}
             */
            family: "required_fields" | "non_empty" | "matches_regex" | "date_compare" | "ratio_gte" | "amount_equal" | "same_subject_value";
            /** Bindings */
            bindings?: components["schemas"]["FieldBinding"][];
            parameters?: components["schemas"]["RuleParameters"];
            severity: components["schemas"]["Severity"];
            /**
             * Needs Clarification
             * @default false
             */
            needs_clarification: boolean;
        };
        /** RuleParameters */
        RuleParameters: {
            /** Factor */
            factor?: string | null;
            /** Pattern */
            pattern?: string | null;
            /** Date Mode */
            date_mode?: ("not_future" | "not_expired") | null;
            /** Field Ids */
            field_ids?: string[];
        };
        /** RuleResult */
        RuleResult: {
            /** Rule Id */
            rule_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "PASS" | "FAIL" | "UNKNOWN" | "NOT_APPLICABLE";
            severity: components["schemas"]["Severity"];
            /** Message */
            message: string;
            /** Operands */
            operands?: {
                [key: string]: components["schemas"]["FieldObservation"];
            };
            /** Formula */
            formula?: string | null;
            /** Sources */
            sources?: components["schemas"]["EvidenceRef"][];
        };
        /** RuleUpdate */
        RuleUpdate: {
            /** Expected Revision */
            expected_revision: number;
            rule: components["schemas"]["RuleDefinition"];
        };
        /** RunProgress */
        RunProgress: {
            /** Total */
            total: number;
            /** Accepted */
            accepted: number;
            /** Determining */
            determining: number;
            /** Checked */
            checked: number;
            /** Processing Error */
            processing_error: number;
        };
        /** RunRequested */
        RunRequested: {
            /**
             * Package Id
             * Format: uuid
             */
            package_id: string;
            /** Input Revision */
            input_revision: number;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
        };
        /**
         * RunStatus
         * @enum {string}
         */
        RunStatus: "queued" | "running" | "completed" | "failed" | "cancelled";
        /** SessionCreate */
        SessionCreate: {
            /** Username */
            username: string;
            /**
             * Password
             * Format: password
             */
            password: string;
        };
        /** SessionResponse */
        SessionResponse: {
            user: components["schemas"]["UserSummary"];
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Csrf Token */
            csrf_token: string;
        };
        /**
         * Severity
         * @enum {string}
         */
        Severity: "info" | "warning" | "error";
        /** SheetCell */
        SheetCell: {
            /** Address */
            address: string;
            /** Value */
            value: string | boolean | null;
            /** Formula */
            formula?: string | null;
            /**
             * Known State
             * @enum {string}
             */
            known_state: "known" | "missing" | "unreadable";
        };
        /** SheetData */
        SheetData: {
            /**
             * File Id
             * Format: uuid
             */
            file_id: string;
            /**
             * File Version Id
             * Format: uuid
             */
            file_version_id: string;
            /** Sheet */
            sheet: string;
            /** Cells */
            cells: components["schemas"]["SheetCell"][];
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
            /** Total */
            total: number;
        };
        /** SheetLocation */
        SheetLocation: {
            /**
             * File Id
             * Format: uuid
             */
            file_id: string;
            /**
             * File Version Id
             * Format: uuid
             */
            file_version_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "sheet";
            /** Sheet */
            sheet: string;
            /** Cell Range */
            cell_range: string;
        };
        /** SourceFragmentRef */
        SourceFragmentRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Location */
            location: components["schemas"]["PageLocation"] | components["schemas"]["SheetLocation"] | components["schemas"]["ParagraphLocation"];
        };
        /**
         * SubjectRole
         * @enum {string}
         */
        SubjectRole: "applicant" | "guarantor" | "person" | "unknown";
        /** TypeUpdate */
        TypeUpdate: {
            /** Expected Revision */
            expected_revision: number;
            document_type: components["schemas"]["DocumentType"];
            /** Reason */
            reason: string;
        };
        /** UploadRejection */
        UploadRejection: {
            /** Original Name */
            original_name: string;
            error: components["schemas"]["ApiError"];
        };
        /** UploadResult */
        UploadResult: {
            /**
             * Package Id
             * Format: uuid
             */
            package_id: string;
            /** Input Revision */
            input_revision: number;
            /** Accepted */
            accepted: components["schemas"]["FileSummary"][];
            /** Rejected */
            rejected: components["schemas"]["UploadRejection"][];
            /** Run Id */
            run_id: string | null;
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
        };
        /** UserSummary */
        UserSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Display Name */
            display_name: string;
            role: components["schemas"]["Role"];
        };
        /**
         * Verdict
         * @enum {string}
         */
        Verdict: "pass" | "review_required" | "issues";
        /** VerificationCreate */
        VerificationCreate: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** VerificationRun */
        VerificationRun: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Package Id
             * Format: uuid
             */
            package_id: string;
            /** Input Revision */
            input_revision: number;
            /** Progress Version */
            progress_version: number;
            status: components["schemas"]["RunStatus"];
            coverage: components["schemas"]["Coverage"];
            freshness: components["schemas"]["Freshness"];
            /**
             * Reference Date
             * Format: date
             */
            reference_date: string;
            /** Timezone */
            timezone: string;
            model_profile: components["schemas"]["ModelProfile"];
            progress: components["schemas"]["RunProgress"];
            /** Files */
            files?: components["schemas"]["FileCheck"][];
            /** Documents */
            documents?: components["schemas"]["DocumentUnit"][];
            report?: components["schemas"]["MachineReport"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    liveness: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LivenessResponse"];
                };
            };
        };
    };
    readiness: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
            /** @description Dependencies not yet ready */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_session: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_session: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    delete_session: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_programs: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProgramSummary_"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_program_versions: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                program_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProgramVersion_"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_packages: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_PackageSummary_"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_package: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PackageCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PackageDetail"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_package: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PackageDetail"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    upload_files: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_files"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadResult"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_configuration: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfigurationUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRequested"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_verification_run: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VerificationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRequested"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_verification_run: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VerificationRun"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    download_file: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                file_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Authorized original; Content-Disposition: attachment */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": Blob;
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_file_preview: {
        parameters: {
            query?: {
                page?: number;
            };
            header?: never;
            path: {
                file_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Authorized preview; Office representations are derivatives */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": Blob;
                    "image/png": Blob;
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_sheet: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                file_id: string;
                sheet: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SheetData"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_document_type: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypeUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRequested"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_document_grouping: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupingUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRequested"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_decision: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApplicationDecision"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_program_drafts: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProgramDraftSummary_"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_program_draft: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProgramDraftCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgramDraft"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_program_draft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgramDraft"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_program_draft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProgramDraftUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgramDraft"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_rule: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RuleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgramDraft"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    validate_program_draft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftValidation"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    publish_program_draft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgramVersion"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_audit: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                package_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AuditEvent_"];
                };
            };
            /** @description Session required or expired */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Access or CSRF check denied */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision or idempotency conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Input exceeds configured limits */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid command */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Contract exists; application handler is not implemented yet */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Required dependency unavailable before acceptance */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
}
