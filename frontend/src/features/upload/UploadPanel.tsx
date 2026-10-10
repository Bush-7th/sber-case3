import { useRef, useState } from "react";
import { File, UploadCloud, X } from "lucide-react";
import { api, ApiError } from "../../shared/api/client";
import { useCommand } from "../../shared/api/queries";
import { bytes, ErrorNotice, Notice } from "../../shared/ui";
import type { Package } from "../../shared/api/contracts";

const allowed = /\.(pdf|doc|docx|xls|xlsx|jpe?g|png)$/i;
export function UploadPanel({ item }: { item: Package }) {
  const [files, setFiles] = useState<File[]>([]);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [duplicateNames, setDuplicateNames] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [receipt, setReceipt] = useState<Awaited<
    ReturnType<typeof api.upload>
  > | null>(null);
  const intent = useRef<{ revision: number; key: string } | null>(null);
  const mutation = useCommand(
    () => {
      intent.current ??= {
        revision: item.input_revision,
        key: crypto.randomUUID(),
      };
      return api.upload(
        item.id,
        intent.current.revision,
        files,
        intent.current.key,
      );
    },
    (result) => {
      setReceipt(result);
      setFiles((current) =>
        current.filter((file) =>
          result.rejected.some((rejected) => rejected.name === file.name),
        ),
      );
      intent.current = null;
    },
  );
  function add(selected: File[]) {
    if (mutation.isPending) return;
    intent.current = null;
    mutation.reset();
    setReceipt(null);
    setInvalid(
      selected.filter((f) => !allowed.test(f.name)).map((f) => f.name),
    );
    const next = [...files];
    const duplicates: string[] = [];
    for (const file of selected.filter(f => allowed.test(f.name))) {
      if (next.some(old => old.name === file.name)) duplicates.push(file.name);
      else next.push(file);
    }
    setDuplicateNames([...new Set(duplicates)]);
    setFiles(next);
  }
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>
            {item.files.length ? "Дозагрузка документов" : "Документы заявки"}
          </h2>
          <p>Можно загрузить несколько файлов и части одного документа.</p>
        </div>
        <span>PDF · DOC · DOCX · XLS · XLSX · JPG · PNG</span>
      </div>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(Array.from(e.dataTransfer.files));
        }}
      >
        <UploadCloud size={30} />
        <strong>Перетащите документы сюда</strong>
        <span>или выберите файлы на компьютере</span>
        <label className="button secondary file-picker">
          Выбрать файлы
          <input
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
            disabled={mutation.isPending}
            onChange={(e) => {
              add(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
        </label>
      </div>
      {invalid.length > 0 && (
        <Notice tone="warning">
          Не добавлены файлы неподдерживаемого формата: {invalid.join(", ")}
        </Notice>
      )}
      {duplicateNames.length > 0 && <Notice tone="warning">
        Файлы с совпадающими именами не добавлены: {duplicateNames.join(", ")}. Переименуйте их или загрузите отдельным пакетом.
      </Notice>}
      {files.length > 0 && (
        <>
          <ul className="selected-files">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`}>
                <File size={17} />
                <span>
                  {file.name}
                  <small>{bytes(file.size)}</small>
                </span>
                <button
                  className="icon-button"
                  aria-label={`Убрать ${file.name}`}
                  disabled={mutation.isPending}
                  onClick={() => {
                    setFiles(files.filter((_, i) => i !== index));
                    intent.current = null;
                    mutation.reset();
                  }}
                >
                  <X size={17} />
                </button>
              </li>
            ))}
          </ul>
          <div className="form-actions">
            <span>
              {files.length} файлов ·{" "}
              {bytes(files.reduce((sum, f) => sum + f.size, 0))}
            </span>
            <button
              className="button primary"
              disabled={mutation.isPending}
              onClick={() => {
                if (
                  mutation.error instanceof ApiError &&
                  mutation.error.status === 409
                )
                  intent.current = null;
                mutation.mutate();
              }}
            >
              {mutation.isPending ? "Загружаем…" : "Загрузить и проверить"}
            </button>
          </div>
        </>
      )}
      <ErrorNotice error={mutation.error} />
      {receipt && (
        <Notice tone={receipt.rejected.length ? "warning" : "success"}>
          Принято файлов: {receipt.accepted.length}.
          {receipt.run_id
            ? " Фоновая проверка запущена."
            : " Новая проверка не запущена."}
          {receipt.rejected.map((r, i) => (
            <p key={i}>
              {r.name}:{" "}
              {r.code === "FILE_TOO_LARGE"
                ? "Превышен размер"
                : r.code === "UNSUPPORTED_FORMAT"
                  ? "Неподдерживаемый формат"
                  : "Файл не принят сервером"}
            </p>
          ))}
        </Notice>
      )}
    </section>
  );
}
