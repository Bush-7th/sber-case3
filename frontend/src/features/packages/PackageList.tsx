import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus, Search } from "lucide-react";
import { api } from "../../shared/api/client";
import { useCommand } from "../../shared/api/queries";
import {
  Badge,
  dateTime,
  decisionLabels,
  Empty,
  ErrorNotice,
  fileCount,
  Loading,
  verdictLabels,
} from "../../shared/ui";
import { initialContext, ProgramFields } from "./ProgramFields";

export function PackageList() {
  const packages = useInfiniteQuery({
    queryKey: ["packages"],
    queryFn: ({ pageParam, signal }) => api.packages(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: 2000,
  });
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [programId, setProgramId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [context, setContext] = useState(initialContext);
  const navigate = useNavigate();
  const create = useCommand(
    () =>
      api.createPackage({
        title: title.trim(),
        program_id: programId,
        program_version_id: versionId,
        context,
      }),
    (item) => navigate(`/packages/${encodeURIComponent(item.id)}`),
  );
  const items = packages.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = items.filter((p) =>
    `${p.title} ${p.program_name}`
      .toLocaleLowerCase("ru")
      .includes(search.toLocaleLowerCase("ru")),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">РАБОЧЕЕ МЕСТО СПЕЦИАЛИСТА</span>
          <h1>Заявки</h1>
          <p>
            Загрузите документы, проверьте результат и зафиксируйте решение.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => setShowCreate(!showCreate)}
        >
          <Plus size={18} />
          {showCreate ? "Закрыть форму" : "Новая заявка"}
        </button>
      </div>
      {showCreate && (
        <section className="panel">
          <div className="section-heading">
            <h2>Новая заявка</h2>
            <span>01 · Программа и контекст</span>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <label>
              Название заявки
              <input
                autoFocus
                required
                maxLength={250}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Организация или название проекта"
                disabled={create.isPending}
              />
            </label>
            <ProgramFields
              programId={programId}
              versionId={versionId}
              context={context}
              onProgram={(id) => {
                setProgramId(id);
                setVersionId("");
              }}
              onVersion={setVersionId}
              onContext={setContext}
              locked={create.isPending}
            />
            <ErrorNotice error={create.error} />
            <div className="form-actions">
              <button
                className="button primary"
                disabled={create.isPending || !versionId || !title.trim()}
              >
                {create.isPending ? "Создаём…" : "Создать заявку"}
                <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </section>
      )}
      <section className="panel list-panel">
        <div className="list-toolbar">
          <h2>
            Все заявки{" "}
            <span className="count">
              {items.length}
              {packages.hasNextPage ? "+" : ""}
            </span>
          </h2>
          <div className="search-field">
            <Search size={17} />
            <input
              aria-label="Поиск по загруженным заявкам"
              placeholder="Поиск по загруженным заявкам"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        <ErrorNotice
          error={packages.error}
          retry={() => void packages.refetch()}
        />
        {packages.isPending ? (
          <Loading />
        ) : filtered.length === 0 ? (
          <Empty title={search ? "Ничего не найдено" : "Пока нет заявок"}>
            {search
              ? "Измените запрос или загрузите следующую страницу."
              : "Создайте первую заявку и выберите программу субсидирования."}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table className="packages-table">
              <thead>
                <tr>
                  <th>Заявка / программа</th>
                  <th>Документы</th>
                  <th>Автоматическая проверка</th>
                  <th>Решение специалиста</th>
                  <th>Обновлено</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        className="row-link"
                        to={`/packages/${encodeURIComponent(item.id)}`}
                      >
                        {item.title}
                        <ArrowRight size={15} />
                      </Link>
                      <small>{item.program_name}</small>
                    </td>
                    <td>{fileCount(item.file_count)}</td>
                    <td>
                      {item.verdict ? (
                        <Badge tone={item.verdict}>
                          {verdictLabels[item.verdict]}
                        </Badge>
                      ) : (
                        <Badge>Ожидает проверки</Badge>
                      )}
                    </td>
                    <td>
                      {item.decision ? (
                        <Badge
                          tone={
                            item.decision.input_revision === item.input_revision
                              ? item.decision.action
                              : "warning"
                          }
                        >
                          {decisionLabels[item.decision.action]}
                          {item.decision.input_revision !== item.input_revision
                            ? " · устарело"
                            : ""}
                        </Badge>
                      ) : (
                        <span className="muted">Не принято</span>
                      )}
                    </td>
                    <td className="date-cell">{dateTime(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {packages.hasNextPage && (
          <div className="form-actions">
            <button
              className="button secondary"
              onClick={() => void packages.fetchNextPage()}
              disabled={packages.isFetchingNextPage}
            >
              Загрузить ещё
            </button>
          </div>
        )}
      </section>
      <div className="page-footer">
        Автоматическая проверка — предварительная оценка. Назначение субсидии
        требует решения специалиста.
      </div>
    </>
  );
}
