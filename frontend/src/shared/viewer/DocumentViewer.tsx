import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
    source?.file_version_id ?? files[0]?.id ?? "",
  );
  const [sheetName, setSheetName] = useState(source?.sheet ?? "");
  useEffect(() => {
    if (source) {
      setSelectedId(source.file_version_id);
      setSheetName(source.sheet ?? "");
    }
  }, [source]);
  const file = files.find((f) => f.id === selectedId) ?? files[0];
  const spreadsheet =
    !!file && ["xls", "xlsx"].includes(file.format.toLowerCase());
  const activeSource = source?.file_version_id === file?.id ? source : null;
  const sheet = useQuery({
    queryKey: ["sheet", file?.id, sheetName],
    queryFn: ({ signal }) => api.sheet(file!.id, sheetName || "_first", signal),
    enabled: spreadsheet,
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
                  : "Исходное содержимое"}
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
              <ErrorNotice
                error={sheet.error}
                retry={() => void sheet.refetch()}
              />
              {sheet.isPending ? (
                <Loading />
              ) : (
                sheet.data && (
                  <>
                    <label>
                      Лист
                      <select
                        value={sheet.data.sheet}
                        onChange={(e) => setSheetName(e.target.value)}
                      >
                        {sheet.data.sheets.map((s) => (
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
                          {sheet.data.cells.map((cell) => (
                            <tr
                              key={cell.address}
                              className={
                                activeSource?.cell_range === cell.address
                                  ? "highlighted-cell"
                                  : ""
                              }
                            >
                              <th>{cell.address}</th>
                              <td>{cell.value ?? "Не найдено"}</td>
                              <td>{cell.formula ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
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
              <iframe
                className="document-frame"
                title={`Просмотр ${file.name}`}
                sandbox="allow-same-origin"
                src={`${api.previewUrl(file.id, activeSource?.page ?? undefined)}${activeSource?.page ? `#page=${activeSource.page}` : ""}`}
              />
            )
          )}
          <p className="form-hint">
            Если превью недоступно, откройте оригинал.
          </p>
        </>
      )}
    </section>
  );
}
