import { useState } from "react";
import { api } from "../../shared/api/client";
import type { Package, Run } from "../../shared/api/contracts";
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
  const [confirmed, setConfirmed] = useState(false);
  const [revision, setRevision] = useState(item.input_revision);
  const decide = useCommand(
    () =>
      api.decide(item.id, {
        expected_revision: revision,
        action,
        reason: reason.trim(),
        report_id:
          currentRun?.input_revision === revision
            ? (currentRun.report?.id ?? null)
            : null,
      }),
    () => {
      setReason("");
      setConfirmed(false);
    },
  );
  function editReason(value: string) {
    if (!reason) setRevision(item.input_revision);
    setReason(value);
    setConfirmed(false);
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
          decide.mutate();
        }}
      >
        <fieldset disabled={decide.isPending}>
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
                      setConfirmed(false);
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
            disabled={decide.isPending}
            onChange={(e) => editReason(e.target.value)}
            placeholder="Зафиксируйте, на чём основано ваше решение"
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            disabled={decide.isPending}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          Я проверил(а) документы и подтверждаю выбранное действие
        </label>
        <ErrorNotice error={decide.error} />
        <div className="form-actions">
          <button
            className="button primary"
            disabled={decide.isPending || !reason.trim() || !confirmed}
          >
            {decide.isPending ? "Сохраняем…" : "Зафиксировать решение"}
          </button>
        </div>
      </form>
      {item.decisions.length > 0 && (
        <div className="result-section">
          <h3>Сохранённые решения</h3>
          {item.decisions.map((decision) => (
            <div className="decision-history" key={decision.id}>
              <Badge
                tone={
                  decision.input_revision === item.input_revision
                    ? decision.action
                    : "warning"
                }
              >
                {decisionLabels[decision.action]}
                {decision.input_revision !== item.input_revision
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
