import { FileCheck2, RefreshCw } from "lucide-react";
import { ApiError, api } from "../../shared/api/client";
import type { Evidence, Package, Run } from "../../shared/api/contracts";
import { useCommand } from "../../shared/api/queries";
import {
  Badge,
  bytes,
  Empty,
  ErrorNotice,
  Issues,
  Notice,
  stageLabels,
  verdictLabels,
} from "../../shared/ui";

export function FileProgress({
  item,
  run,
  historical,
}: {
  item: Package;
  run: Run | undefined;
  historical: boolean;
}) {
  const verify = useCommand((fileId: string) =>
    api.verify(item.id, item.input_revision, fileId),
  );
  const files = run?.files ?? item.files;
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Ход обработки</h2>
        <span>
          {run
            ? `${run.progress.terminal} из ${run.progress.accepted} завершены`
            : `${files.length} файлов`}
        </span>
      </div>
      <ErrorNotice error={verify.error} />
      {!files.length ? (
        <Empty title="Документы ещё не загружены">
          Добавьте файлы для проверки.
        </Empty>
      ) : (
        <ul className="file-progress">
          {files.map((file) => (
            <li key={file.id}>
              <div className="file-symbol">
                <FileCheck2 size={19} />
              </div>
              <div className="file-info">
                <strong>{file.name}</strong>
                <small>
                  {file.format.toUpperCase()} · {bytes(file.size_bytes)}
                </small>
                {file.error && (
                  <ErrorNotice
                    error={
                      new ApiError(
                        200,
                        file.error.code,
                        file.error.correlation_id ?? undefined,
                      )
                    }
                  />
                )}
              </div>
              <div className="file-status">
                <Badge
                  tone={
                    file.processing === "processing_error"
                      ? "error"
                      : file.processing === "checked"
                        ? "success"
                        : "neutral"
                  }
                >
                  {file.processing === "accepted"
                    ? "Принят"
                    : file.processing === "checked"
                      ? "Проверен"
                      : file.processing === "processing_error"
                        ? "Ошибка обработки"
                        : "Определяется"}
                </Badge>
                {file.processing_stage && (
                  <small>{stageLabels[file.processing_stage]}</small>
                )}
                {file.verdict && <small>{verdictLabels[file.verdict]}</small>}
                {file.error?.retryable && !historical && (
                  <button
                    className="button secondary compact"
                    disabled={verify.isPending}
                    onClick={() => verify.mutate(file.id)}
                  >
                    <RefreshCw size={13} />
                    Повторить
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
export function RunResult({
  run,
  stale,
  onSource,
}: {
  run: Run | undefined;
  stale: boolean;
  onSource: (source: Evidence) => void;
}) {
  if (!run)
    return (
      <section className="panel">
        <Empty title="Проверка ещё не началась">
          Результаты появятся после приёма документов сервером.
        </Empty>
      </section>
    );
  const report = run.report;
  const inconsistentPass =
    report?.verdict === "pass" &&
    (run.provisional ||
      run.coverage !== "complete" ||
      run.status !== "completed");
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Автоматическая проверка</h2>
          <p>Оценка на основе извлечённых машиной данных</p>
        </div>
        {report && run.status !== "failed" && (
          <Badge tone={stale || inconsistentPass ? "warning" : report.verdict}>
            {inconsistentPass
              ? "Итог не подтверждён"
              : verdictLabels[report.verdict]}
          </Badge>
        )}
      </div>
      {inconsistentPass && (
        <Notice tone="error">
          Серверный результат противоречит полноте обработки. Успешная проверка
          не подтверждена; требуется сверка с администратором.
        </Notice>
      )}
      {stale && (
        <Notice tone="warning">
          Исторический результат. Он не отражает текущую ревизию заявки.
        </Notice>
      )}
      {(run.provisional || run.coverage !== "complete") && (
        <Notice tone="warning">
          Предварительный результат: часть файлов ещё не обработана или требует
          внимания. Состав и междокументные проверки могут измениться.
        </Notice>
      )}
      {run.status === "failed" && (
        <Notice tone="error">
          Запуск завершился техническим сбоем. Итоговой предметной оценки нет;
          частичные результаты доступны.
        </Notice>
      )}
      {report && run.status !== "failed" && (
        <>
          <div className="result-section">
            <h3>Комплектность пакета</h3>
            <div className="requirement-grid">
              {report.requirements.map((requirement, i) => (
                <div key={i} className="requirement-row">
                  <Badge
                    tone={
                      requirement.status === "found"
                        ? "success"
                        : requirement.status === "missing"
                          ? requirement.kind === "conditional"
                            ? "warning"
                            : "error"
                          : "neutral"
                    }
                  >
                    {
                      {
                        found: "Найден",
                        missing: "Отсутствует",
                        pending: "Ожидается",
                        unknown: "Неизвестно",
                        not_applicable: "Не требуется",
                      }[requirement.status]
                    }
                  </Badge>
                  <div>
                    <strong>{requirement.message}</strong>
                    <small>
                      {
                        {
                          required: "Обязательный документ",
                          conditional: "Условный документ",
                          optional: "Дополнительный документ",
                        }[requirement.kind]
                      }
                    </small>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="result-section">
            <h3>Проверка правил</h3>
            {report.rules.map((rule) => (
              <div className="rule-result" key={rule.id}>
                <Badge
                  tone={
                    rule.status === "PASS"
                      ? "success"
                      : rule.status === "FAIL"
                        ? "error"
                        : "warning"
                  }
                >
                  {
                    {
                      PASS: "Пройдено",
                      FAIL: "Нарушение",
                      UNKNOWN: "Не определено",
                      NOT_APPLICABLE: "Не применимо",
                    }[rule.status]
                  }
                </Badge>
                <div>
                  <strong>{rule.name}</strong>
                  <p>{rule.explanation}</p>
                  <div className="source-links">
                    {rule.sources.map((source, i) => (
                      <button
                        className="text-link"
                        key={i}
                        onClick={() => onSource(source)}
                      >
                        Источник {i + 1}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Issues issues={report.issues} />
        </>
      )}
      {!report && (
        <p className="muted">
          {run.status === "queued"
            ? "Проверка поставлена в очередь."
            : "Отчёт пока не сформирован."}
        </p>
      )}
      {run.provider && (
        <p className="form-hint">
          Провайдер: {run.provider.provider} · Модель: {run.provider.model}
        </p>
      )}
    </section>
  );
}
