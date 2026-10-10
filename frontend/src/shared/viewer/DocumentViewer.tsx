import { useEffect, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ExternalLink, FileSearch } from "lucide-react";
import type { Evidence, FileCheck } from "../api/contracts";
import { api } from "../api/client";
import { Empty, ErrorNotice, Loading, Notice } from "../ui";

export function sourceLabel(source: Evidence) {
  return (
    [
      source.page ? `Страница ${source.page}` : null,
      source.sheet ? `Лист «${source.sheet}»` : null,
      source.cell_range,
      source.paragraph ? `Абзац ${source.paragraph}` : null,
    ]
      .filter(Boolean)
      .join(" · ") || "Источник без точного адреса"
  );
}
export function DocumentViewer({
  files,
  source,
}: {
  files: FileCheck[];
  source: Evidence | null;
}) {
  const [selectedId, setSelectedId] = useState(
    source?.file_id ?? files[0]?.id ?? "",
  );
  const [sheetName, setSheetName] = useState(source?.sheet ?? "");
  const [pageNumber, setPageNumber] = useState(source?.page ?? 1);
  useEffect(() => {
    if (source) {
      setSelectedId(source.file_id);
      setSheetName(source.sheet ?? "");
      setPageNumber(source.page ?? 1);
    }
  }, [source]);
  const file = files.find((f) => f.id === selectedId) ?? (source ? undefined : files[0]);
  const spreadsheet =
    !!file && ["xls", "xlsx"].includes(file.format.toLowerCase());
  const activeSource = source?.file_version_id === file?.file_version_id ? source : null;
  const activeSheet = sheetName || file?.sheet_names[0] || "";
  const sheet = useInfiniteQuery({
    queryKey: ["sheet", file?.id, file?.file_version_id, activeSheet],
    queryFn: ({ signal, pageParam }) => api.sheet(file!.id, activeSheet, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: page => page.offset + page.cells.length < page.total ? page.offset + page.cells.length : undefined,
    enabled: spreadsheet && !!activeSheet,
  });
  return (
    <section className="panel viewer-panel">
      <div className="section-heading">
        <h2>
          <FileSearch size={18} />
          Источник документа
        </h2>
        {file && (
          <a
            className="text-link"
            href={api.contentUrl(file.id)}
            target="_blank"
            rel="noreferrer"
          >
            Оригинал
            <ExternalLink size={14} />
          </a>
        )}
      </div>
      {files.length === 0 ? (
        <Empty title="Нет документов">Исходник появится после загрузки.</Empty>
      ) : (
        <>
          <label className="viewer-select">
            Файл
            <select
              value={file?.id ?? ""}
              onChange={(e) => {
                setSelectedId(e.target.value);
                setSheetName("");
                setPageNumber(1);
              }}
            >
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
          {activeSource && (
            <div className="source-caption">
              <strong>{sourceLabel(activeSource)}</strong>
              <span>
                {activeSource.method === "ocr"
                  ? "Распознанный текст"
                  : activeSource.method === "vision" ? "Извлечено из изображения" : "Исходное содержимое"}
              </span>
              {activeSource.quote && (
                <blockquote>{activeSource.quote}</blockquote>
              )}
            </div>
          )}
          {file && ["doc", "docx"].includes(file.format.toLowerCase()) && (
            <Notice>
              Это производное превью Office. Для проверки вёрстки доступен
              оригинал.
            </Notice>
          )}
          {spreadsheet ? (
            <>
              {!activeSheet && <Notice>Имена листов появятся после подготовки таблицы.</Notice>}
              <ErrorNotice
                error={sheet.error}
                retry={() => void sheet.refetch()}
              />
              {sheet.isPending && activeSheet ? (
                <Loading />
              ) : (
                sheet.data && (
                  <>
                    <label>
                      Лист
                      <select
                        aria-label="Лист"
                        value={activeSheet}
                        onChange={(e) => setSheetName(e.target.value)}
                      >
                        {file?.sheet_names.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                    <div className="table-scroll sheet-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Ячейка</th>
                            <th>Значение</th>
                            <th>Формула</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sheet.data.pages.flatMap(p => p.cells).map((cell) => (
                            <tr
                              key={cell.address}
                              className={
                                activeSource?.sheet === activeSheet && activeSource?.cell_range === cell.address
                                  ? "highlighted-cell"
                                  : ""
                              }
                            >
                              <th>{cell.address}</th>
                              <td>{cell.known_state === "unreadable" ? "Не прочитано" : cell.value ?? "Не найдено"}</td>
                              <td>{cell.formula ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {sheet.hasNextPage && <button className="button secondary compact" disabled={sheet.isFetchingNextPage} onClick={() => void sheet.fetchNextPage()}>Загрузить ещё ячейки</button>}
                    <p className="form-hint">
                      Адрес источника: {activeSource?.cell_range ?? "не выбран"}
                      . Значение без сохранённого результата формулы остаётся
                      неизвестным.
                    </p>
                  </>
                )
              )}
            </>
          ) : (
            file && (
              <>
              {(file.page_count ?? 0) > 1 && <label>Страница
                <select value={Math.min(pageNumber, file.page_count ?? pageNumber)} onChange={e => setPageNumber(Number(e.target.value))}>
                  {Array.from({ length: file.page_count! }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
                </select>
              </label>}
              <iframe
                className="document-frame"
                title={`Просмотр ${file.name}`}
                sandbox="allow-same-origin"
                src={api.previewUrl(file.id, Math.min(pageNumber, file.page_count ?? pageNumber))}
              />
              </>
            )
          )}
          <p className="form-hint">
            Если превью недоступно, откройте оригинал.
          </p>
          {!file && <Notice tone="warning">Файл выбранного источника отсутствует в этом снимке. Откройте соответствующий сохранённый запуск.</Notice>}
        </>
      )}
    </section>
  );
}
