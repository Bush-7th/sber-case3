import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw, Settings2 } from "lucide-react";
import { api } from "../../shared/api/client";
import type { Evidence, Package } from "../../shared/api/contracts";
import { useCommand } from "../../shared/api/queries";
import {
  Badge,
  dateTime,
  Empty,
  ErrorNotice,
  Loading,
  Notice,
} from "../../shared/ui";
import { DocumentViewer } from "../../shared/viewer/DocumentViewer";
import { UploadPanel } from "../upload/UploadPanel";
import { FileProgress, RunResult } from "../results/RunResult";
import { DocumentReview } from "../review/DocumentReview";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { ProgramFields } from "./ProgramFields";

function Configuration({ item, close }: { item: Package; close: () => void }) {
  const [context, setContext] = useState(item.context);
  const [version, setVersion] = useState(item.program_version_id);
  const [revision] = useState(item.input_revision);
  const save = useCommand(
    () =>
      api.configure(item.id, {
        expected_revision: revision,
        program_version_id: version,
        context,
      }),
    close,
  );
  return (
    <section className="panel">
      <h2>Программа и контекст</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <ProgramFields
          programId={item.program_id}
          versionId={version}
          context={context}
          onVersion={setVersion}
          onContext={setContext}
          locked={save.isPending}
        />
        <Notice>
          Применение редакции или изменение контекста создаст новую ревизию и
          проверку всех файлов заявки.
        </Notice>
        <ErrorNotice error={save.error} />
        <div className="form-actions">
          <button
            className="button secondary"
            type="button"
            onClick={close}
            disabled={save.isPending}
          >
            Отмена
          </button>
          <button
            className="button primary"
            disabled={save.isPending || !version}
          >
            Применить и перепроверить
          </button>
        </div>
      </form>
    </section>
  );
}
export function PackageWorkspace() {
  const { id = "" } = useParams();
  return <Workspace key={id} id={id} />;
}
function Workspace({ id }: { id: string }) {
  const item = useQuery({
    queryKey: ["package", id],
    queryFn: ({ signal }) => api.package(id, signal),
    refetchInterval: 2000,
  });
  const [historyRun, setHistoryRun] = useState("");
  const [source, setSource] = useState<Evidence | null>(null);
  const [configuration, setConfiguration] = useState(false);
  const runId = historyRun || item.data?.requested_run_id;
  const run = useQuery({
    queryKey: ["run", runId, item.data?.input_revision],
    queryFn: ({ signal }) => api.run(runId!, signal),
    enabled: !!runId,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 2000
        : false,
  });
  const audit = useQuery({
    queryKey: ["audit", id, item.data?.input_revision],
    queryFn: ({ signal }) => api.audit(id, signal),
  });
  const verify = useCommand(() => api.verify(id, item.data!.input_revision));
  if (item.isPending) return <Loading />;
  if (!item.data)
    return (
      <>
        <Link className="back-link" to="/packages">
          <ArrowLeft size={15} />К заявкам
        </Link>
        <ErrorNotice error={item.error} retry={() => void item.refetch()} />
      </>
    );
  const pkg = item.data;
  const stale =
    !!run.data &&
    (run.data.input_revision !== pkg.input_revision ||
      run.data.id !== pkg.requested_run_id ||
      run.data.freshness !== "current");
  return (
    <>
      <Link className="back-link" to="/packages">
        <ArrowLeft size={15} />
        Все заявки
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{pkg.program_name}</span>
          <h1>{pkg.title}</h1>
          <p>
            Ревизия {pkg.input_revision} · Обновлено {dateTime(pkg.updated_at)}
          </p>
        </div>
        <div className="heading-actions">
          <button
            className="button secondary"
            onClick={() => setConfiguration(!configuration)}
          >
            <Settings2 size={16} />
            Настройки заявки
          </button>
          <button
            className="button primary"
            disabled={verify.isPending || !pkg.files.length}
            onClick={() => verify.mutate()}
          >
            <RefreshCw size={16} />
            {verify.isPending ? "Запускаем…" : "Перепроверить"}
          </button>
        </div>
      </div>
      <ErrorNotice error={item.error || verify.error} />
      {configuration && (
        <Configuration item={pkg} close={() => setConfiguration(false)} />
      )}
      <UploadPanel item={pkg} />
      <div className="workspace-grid">
        <div className="workspace-results">
          <div className="run-toolbar">
            <label>
              Отчёт
              <select
                value={historyRun}
                onChange={(e) => {
                  setHistoryRun(e.target.value);
                  setSource(null);
                }}
              >
                <option value="">Текущая проверка</option>
                {pkg.report_history.map((report) => (
                  <option value={report.run_id} key={report.run_id}>
                    Ревизия {report.input_revision} ·{" "}
                    {dateTime(report.created_at)}
                  </option>
                ))}
              </select>
            </label>
            {run.data && (
              <Badge>
                {
                  {
                    queued: "В очереди",
                    running: "Обрабатывается",
                    completed: "Завершён",
                    failed: "Сбой запуска",
                    cancelled: "Отменён",
                  }[run.data.status]
                }
              </Badge>
            )}
          </div>
          <ErrorNotice error={run.error} retry={() => void run.refetch()} />
          {run.isFetching && !run.data && runId && <Loading />}
          <FileProgress
            item={pkg}
            run={run.data}
            historical={stale || !!historyRun}
          />
          <RunResult run={run.data} stale={stale} onSource={setSource} />
          {run.data?.document_units.map((unit) => (
            <DocumentReview
              key={`${unit.id}-${run.data!.id}`}
              unit={unit}
              item={pkg}
              stale={stale || !!historyRun}
              onSource={setSource}
            />
          ))}
          {run.data && run.data.document_units.length === 0 && (
            <section className="panel">
              <Empty title="Документы ещё не определены">
                Найденные поля появятся по мере обработки файлов.
              </Empty>
            </section>
          )}
        </div>
        <div className="workspace-source">
          <DocumentViewer
            files={run.data?.files ?? pkg.files}
            source={source}
          />
        </div>
      </div>
      {historyRun && (
        <Notice>
          Вы просматриваете сохранённый отчёт. Для фиксации решения откройте
          текущую проверку.
        </Notice>
      )}
      {!historyRun && (
        <DecisionPanel item={pkg} currentRun={stale ? undefined : run.data} />
      )}
      <section className="panel">
        <h2>Журнал заявки</h2>
        <ErrorNotice error={audit.error} retry={() => void audit.refetch()} />
        {audit.data?.items.length ? (
          <ol className="audit-list">
            {audit.data.items.map((event) => (
              <li key={event.id}>
                <span className="audit-dot" />
                <div>
                  <strong>{event.message}</strong>
                  <small>
                    {event.actor} · {dateTime(event.created_at)}
                    {event.input_revision !== null
                      ? ` · Ревизия ${event.input_revision}`
                      : ""}
                  </small>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">События ещё не получены.</p>
        )}
      </section>
    </>
  );
}
