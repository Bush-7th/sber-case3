import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type {
  DocumentUnit,
  Evidence,
  Package,
} from "../../shared/api/contracts";
import { useCommand } from "../../shared/api/queries";
import { Badge, ErrorNotice, Issues, Notice } from "../../shared/ui";
import { sourceLabel } from "../../shared/viewer/DocumentViewer";

function ReviewEditor({
  unit,
  item,
  close,
  fragments,
}: {
  unit: DocumentUnit;
  item: Package;
  close: () => void;
  fragments: DocumentUnit["fragments"];
}) {
  const types = useQuery({
    queryKey: ["document-types", item.program_id, item.program_version_id],
    queryFn: ({ signal }) => api.documentTypes(item.program_id, item.program_version_id, signal),
  });
  const [type, setType] = useState(unit.effective_type ?? "");
  const [reason, setReason] = useState("");
  const [ids, setIds] = useState(unit.fragments.map(f => f.id));
  const [revision, setRevision] = useState(item.input_revision);
  const changeType = useCommand(
    () => api.type(unit.id, revision, type, reason.trim()),
    close,
  );
  const changeGrouping = useCommand(
    () => api.grouping(unit.id, revision, ids, reason.trim()),
    close,
  );
  const pending = changeType.isPending || changeGrouping.isPending;
  return (
    <div className="review-editor">
      <Notice>
        Правка создаст новую ревизию и проверку. Поля заново извлечёт модель;
        прежний автоматический результат сохранится в истории.
      </Notice>
      <label>
        Тип документа
        <select
          required
          value={type}
          disabled={pending}
          onChange={(e) => setType(e.target.value)}
        >
          <option value="">Выберите тип</option>
          {types.data?.items.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
              {t.extension ? " · расширение" : ""}
            </option>
          ))}
        </select>
      </label>
      <fieldset disabled={pending}>
        <legend>Состав логического документа</legend>
        {fragments.map((fragment) => (
          <label className="checkbox-label" key={fragment.id}>
            <input
              type="checkbox"
              checked={ids.includes(fragment.id)}
              onChange={(e) =>
                setIds(
                  e.target.checked
                    ? [...ids, fragment.id]
                    : ids.filter((id) => id !== fragment.id),
                )
              }
            />
            {item.files.find(f => f.file_version_id === fragment.source.file_version_id)?.name ?? fragment.source.file_version_id} · {sourceLabel(fragment.source)}
          </label>
        ))}
      </fieldset>
      <label>
        Основание изменения
        <textarea
          required
          value={reason}
          disabled={pending}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Почему меняете тип или состав документа"
        />
      </label>
      <ErrorNotice
        error={types.error || changeType.error || changeGrouping.error}
      />
      {revision !== item.input_revision && <Notice tone="warning">
        Заявка обновилась. Сверьте тип и состав по актуальной проверке.
        <button className="button secondary" onClick={() => { setRevision(item.input_revision); changeType.reset(); changeGrouping.reset(); }}>Сверено: использовать актуальную ревизию</button>
      </Notice>}
      <div className="form-actions">
        <button className="button secondary" onClick={close} disabled={pending}>
          Отмена
        </button>
        <button
          className="button secondary"
          disabled={pending || !ids.length || !reason.trim() || revision !== item.input_revision || ids.some(id => !fragments.some(f => f.id === id))}
          onClick={() => changeGrouping.mutate()}
        >
          Подтвердить состав
        </button>
        <button
          className="button primary"
          disabled={pending || !type || !reason.trim() || revision !== item.input_revision}
          onClick={() => changeType.mutate()}
        >
          Сохранить тип и перепроверить
        </button>
      </div>
    </div>
  );
}
export function DocumentReview({
  unit,
  item,
  stale,
  onSource,
  fragments,
}: {
  unit: DocumentUnit;
  item: Package;
  stale: boolean;
  onSource: (source: Evidence) => void;
  fragments: DocumentUnit["fragments"];
}) {
  const [editing, setEditing] = useState(false);
  const types = useQuery({
    queryKey: ["document-types", item.program_id, item.program_version_id],
    queryFn: ({ signal }) => api.documentTypes(item.program_id, item.program_version_id, signal),
  });
  const typeLabel = (id: string | null) =>
    types.data?.items.find((type) => type.id === id)?.name ??
    (id ? "Тип из каталога" : "Тип не определён");
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>{typeLabel(unit.effective_type)}</h2>
          <p>
            {unit.file_version_ids.length} файлов · Машинный тип:{" "}
            {typeLabel(unit.predicted_type)}
          </p>
        </div>
        {!stale && (
          <button
            className="button secondary compact"
            onClick={() => setEditing(!editing)}
          >
            Исправить тип / состав
          </button>
        )}
      </div>
      {unit.type_overridden && (
        <Notice>
          Тип изменён специалистом. Автор и основание доступны в журнале заявки.
        </Notice>
      )}
      {editing && !stale ? (
        <ReviewEditor unit={unit} item={item} fragments={fragments} close={() => setEditing(false)} />
      ) : (
        <>
          <div className="field-list">
            {unit.fields.map((field) => (
              <div className="field-row" key={field.key}>
                <span>{field.label}</span>
                <div>
                  <strong>{field.value ?? "Не найдено"}</strong>
                  {field.known_state !== "known" && (
                    <Badge tone="warning">
                      {
                        {
                          missing: "Не найдено",
                          unknown: "Не определено",
                          conflict: "Конфликт источников",
                        }[field.known_state]
                      }
                    </Badge>
                  )}
                  {field.value !== null && !field.sources.length && (
                    <small>
                      Источник не предоставлен. Значение требует сверки.
                    </small>
                  )}
                  <div className="source-links">
                    {field.sources.map((source, i) => (
                      <button
                        key={i}
                        className="text-link"
                        onClick={() => onSource(source)}
                      >
                        {sourceLabel(source)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Issues issues={unit.issues} />
        </>
      )}
    </section>
  );
}
