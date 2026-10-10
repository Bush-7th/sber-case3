import { useState } from "react";
import { api } from "../../shared/api/client";
import type { Package, Run } from "../../shared/api/contracts";
import { ApiError } from "../../shared/api/client";
import type { components } from "../../shared/api/schema";
import { useCommand } from "../../shared/api/queries";
import {
  Badge,
  dateTime,
  decisionLabels,
  ErrorNotice,
  Notice,
} from "../../shared/ui";

export function DecisionPanel({
  item,
  currentRun,
}: {
  item: Package;
  currentRun?: Run;
}) {
  const [action, setAction] = useState<
    "accepted" | "needs_revision" | "rejected"
  >("needs_revision");
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState<{ key: string; reportId: string | null } | null>(null);
  const [revision, setRevision] = useState(item.input_revision);
  const [intent, setIntent] = useState<components["schemas"]["DecisionCreate"] | null>(null);
  const basisKey = JSON.stringify([revision, item.input_revision, currentRun?.id, currentRun?.report?.id, currentRun?.progress_version]);
  const confirmed = confirmation?.key === basisKey;
  const decide = useCommand(
    (body: components["schemas"]["DecisionCreate"]) => api.decide(item.id, body),
    () => {
      setReason("");
      setConfirmation(null);
      setIntent(null);
    },
  );
  const ambiguous = !!intent && !!decide.error && !(decide.error instanceof ApiError && decide.error.status >= 400 && decide.error.status < 500);
  const locked = decide.isPending || ambiguous;
  function editReason(value: string) {
    if (!reason) setRevision(item.input_revision);
    setReason(value);
    setConfirmation(null);
  }
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Решение специалиста</h2>
        <span>Отдельно от автоматической оценки</span>
      </div>
      <Notice>
        Система не принимает заявку автоматически. Решение сохраняется с
        автором, основанием и ревизией.
      </Notice>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (ambiguous && intent) { decide.mutate(intent); return; }
          if (!confirmed || revision !== item.input_revision) return;
          const body = { expected_revision: revision, action, reason: reason.trim(), report_id: confirmation!.reportId };
          setIntent(body);
          decide.mutate(body);
        }}
      >
        <fieldset disabled={locked}>
          <legend>Выберите действие</legend>
          <div className="decision-options">
            {(["accepted", "needs_revision", "rejected"] as const).map(
              (option) => (
                <label
                  className={`decision-option ${action === option ? "selected" : ""}`}
                  key={option}
                >
                  <input
                    type="radio"
                    name="decision"
                    checked={action === option}
                    onChange={() => {
                      setAction(option);
                      setConfirmation(null);
                    }}
                  />
                  {
                    {
                      accepted: "Принять",
                      needs_revision: "Вернуть на доработку",
                      rejected: "Отклонить",
                    }[option]
                  }
                </label>
              ),
            )}
          </div>
        </fieldset>
        <label>
          Основание решения
          <textarea
            required
            maxLength={5000}
            value={reason}
            disabled={locked}
            onChange={(e) => editReason(e.target.value)}
            placeholder="Зафиксируйте, на чём основано ваше решение"
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            disabled={locked || revision !== item.input_revision}
            onChange={(e) => setConfirmation(e.target.checked ? { key: basisKey, reportId: currentRun?.input_revision === revision ? currentRun.report?.id ?? null : null } : null)}
          />
          Я проверил(а) документы и подтверждаю выбранное действие
        </label>
        <ErrorNotice error={decide.error} />
        {confirmation && !confirmed && !ambiguous && <Notice tone="warning">Отчёт или ревизия изменились. Сверьте результат и подтвердите решение заново.</Notice>}
        {revision !== item.input_revision && !ambiguous && <Notice tone="warning">
          Заявка обновилась до ревизии {item.input_revision}. Основание сохранено; сверьте его с актуальными документами.
          <button type="button" className="button secondary" onClick={() => { setRevision(item.input_revision); setConfirmation(null); setIntent(null); decide.reset(); }}>
            Сверено: использовать актуальную ревизию
          </button>
        </Notice>}
        {ambiguous && <Notice tone="warning">Сервер мог сохранить решение. Повтор отправит ту же команду и ключ, с исходной ревизией и отчётом.</Notice>}
        <div className="form-actions">
          <button
            className="button primary"
            disabled={decide.isPending || (!ambiguous && (!reason.trim() || !confirmed || revision !== item.input_revision))}
          >
            {decide.isPending ? "Сохраняем…" : ambiguous ? "Повторить сохранение решения" : "Зафиксировать решение"}
          </button>
        </div>
      </form>
      {item.decisions.length > 0 && (
        <div className="result-section">
          <h3>Текущее сохранённое решение</h3>
          {item.decisions.map((decision) => (
            <div className="decision-history" key={decision.id}>
              <Badge
                tone={
                  decision.input_revision === item.input_revision && decision.freshness === "current"
                    ? decision.action
                    : "warning"
                }
              >
                {decisionLabels[decision.action]}
                {decision.input_revision !== item.input_revision || decision.freshness !== "current"
                  ? " · устарело"
                  : ""}
              </Badge>
              <p>{decision.reason}</p>
              <small>
                {decision.author} · {dateTime(decision.created_at)} · Ревизия{" "}
                {decision.input_revision}
              </small>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
