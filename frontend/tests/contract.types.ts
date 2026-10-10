import { createApiClient } from "../src/shared/api/index.js";
import type { components } from "../src/shared/api/schema.js";

const api = createApiClient({ getCsrfToken: () => "csrf" });

function checkContracts() {
  void api.http.POST("/api/v1/packages/{package_id}/decisions", {
    params: { path: { package_id: "id" }, header: { "Idempotency-Key": "key" } },
    body: { expected_revision: 1, action: "accepted", reason: "Reviewed" },
  });
  const wrongDecision: components["schemas"]["DecisionCreate"] = {
    expected_revision: 1, reason: "Reviewed",
    // @ts-expect-error A machine verdict is not a specialist decision.
    action: "pass",
  };
  const wrongAmount: components["schemas"]["ExpenseItem"] = {
    description: "Line", evidence: [], unit: null,
    // @ts-expect-error Decimal values travel as strings, not JS numbers.
    amount: 10,
  };
  // @ts-expect-error Endpoints must exist in the generated OpenAPI contract.
  void api.http.GET("/api/v1/unknown");
  return { wrongDecision, wrongAmount };
}

void checkContracts;
