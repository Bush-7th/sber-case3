import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Plus, Save, Send, Trash2 } from "lucide-react";
import { api } from "../../shared/api/client";
import type { ProgramDraft, RuleDefinition } from "../../shared/api/contracts";
import { useCommand } from "../../shared/api/queries";
import {
  Badge,
  Empty,
  ErrorNotice,
  Issues,
  Loading,
  Notice,
} from "../../shared/ui";

const familyLabels: Record<RuleDefinition["family"], string> = {
  required_fields: "Обязательные поля",
  non_empty: "Непустое значение",
  matches_regex: "Формат значения",
  date_compare: "Сравнение дат",
  ratio_gte: "Доля собственных средств",
  amount_equal: "Равенство сумм",
  same_subject_value: "Одинаковое значение заявителя",
};
const parameterKeys: Record<RuleDefinition["family"], string[]> = {
  required_fields: ["field_ids"],
  non_empty: [],
  matches_regex: ["pattern"],
  date_compare: ["date_mode"],
  ratio_gte: ["factor"],
  amount_equal: [],
  same_subject_value: [],
};
const parameterLabels: Record<string, string> = {
  field_ids: "Поля (через запятую)",
  pattern: "Шаблон полного совпадения",
  date_mode: "Проверка даты",
  reference: "Дата сравнения",
  factor: "Минимальная доля (0.50 = 50%)",
  subject_role: "Роль организации",
};

type Predicate = NonNullable<ProgramDraft["definition"]["requirements"][number]["predicate"]>;
function ConditionEditor({ value, onChange }: { value: Predicate | null; onChange: (value: Predicate | null) => void }) {
  return <div className="condition-editor">
    <label>Условие
      <select value={value?.kind ?? "none"} onChange={e => {
        const kind = e.target.value;
        onChange(kind === "none" ? null : kind === "equals" ? { kind, field: "project_type", value: "" } : kind === "is_true" ? { kind, field: "certificate_required" } : { kind: kind as "all" | "any", operands: [{ kind: "is_true", field: "certificate_required" }] });
      }}>
        <option value="none">Не задано</option><option value="is_true">Поле = да</option><option value="equals">Поле равно значению</option><option value="all">Все условия</option><option value="any">Хотя бы одно условие</option>
      </select>
    </label>
    {value && "field" in value && <label>Поле условия
      <input required value={value.field} onChange={e => onChange({ ...value, field: e.target.value })} list="context-fields" />
    </label>}
    {value?.kind === "equals" && <>
      <label>Тип значения<select value={typeof value.value} onChange={e => onChange({ ...value, value: e.target.value === "boolean" ? true : "" })}><option value="string">Текст</option><option value="boolean">Да / нет</option></select></label>
      <label>Значение{typeof value.value === "boolean" ? <select value={String(value.value)} onChange={e => onChange({ ...value, value: e.target.value === "true" })}><option value="true">Да</option><option value="false">Нет</option></select> : <input required value={value.value} onChange={e => onChange({ ...value, value: e.target.value })} />}</label>
    </>}
    {value && "operands" in value && <>
      {value.operands.map((child, index) => <div key={index} className="condition-child">
        <ConditionEditor value={child} onChange={next => { if (next) onChange({ ...value, operands: value.operands.map((v, i) => i === index ? next : v) }); }} />
        <button type="button" className="text-link" disabled={value.operands.length === 1} onClick={() => onChange({ ...value, operands: value.operands.filter((_, i) => i !== index) })}>Удалить условие {index + 1}</button>
      </div>)}
      <button type="button" className="text-link" onClick={() => onChange({ ...value, operands: [...value.operands, { kind: "is_true", field: "gims_required" }] })}>Добавить условие</button>
    </>}
  </div>;
}
function DraftEditor({ original }: { original: ProgramDraft }) {
  const [definition, setDefinition] = useState(original.definition);
  const [revision, setRevision] = useState(original.revision);
  const draft = { ...definition, row_version: revision };
  const toWire = () => ({ ...original, revision, definition });
  const [dirty, setDirty] = useState(false);
  const [validatedVersion, setValidatedVersion] = useState<number | null>(null);
  const [published, setPublished] = useState("");
  const types = { data: { items: draft.document_types.map(t => ({ id: t.id, name: t.label, extension: t.extension })) }, error: null };
  const save = useCommand(
    () => api.saveDraft(toWire()),
    (saved) => {
      setDefinition(saved.definition);
      setRevision(saved.revision);
      setDirty(false);
      setValidatedVersion(null);
    },
  );
  const validate = useCommand(
    () => api.validateDraft(toWire()),
    (result) => setValidatedVersion(result.valid ? result.revision : null),
  );
  const publish = useCommand(
    () => api.publishDraft(toWire()),
    (version) => setPublished(version.label),
  );
  const pending = save.isPending || validate.isPending || publish.isPending;
  function change(next: ProgramDraft["definition"] & { row_version: number }) {
    const { row_version: _revision, ...updated } = next;
    setDefinition(updated);
    setDirty(true);
    setValidatedVersion(null);
    validate.reset();
  }
  function changeRule(index: number, rule: RuleDefinition) {
    change({
      ...draft,
      rules: draft.rules.map((old, i) => (i === index ? rule : old)),
    });
  }
  if (published)
    return (
      <section className="panel">
        <Notice tone="success">
          Редакция «{published}» опубликована. Специалист может применить её к
          заявке и перепроверить те же документы.
        </Notice>
      </section>
    );
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>{draft.name}</h2>
          <p>
            Черновик · версия изменений {draft.row_version}
            {dirty ? " · есть несохранённые изменения" : ""}
          </p>
        </div>
        <Badge>Черновик</Badge>
      </div>
      {original.revision > draft.row_version && (
        <Notice tone="warning">
          Черновик изменён другим участником. Сверьте введённые данные перед
          загрузкой новой версии.
          <button
            type="button"
            className="button secondary compact"
            onClick={() => {
              setDefinition(original.definition);
              setRevision(original.revision);
              setDirty(false);
              setValidatedVersion(null);
              save.reset();
              validate.reset();
            }}
          >
            Загрузить актуальный черновик
          </button>
        </Notice>
      )}
      <Notice>
        Опубликованная редакция неизменяема. Для проверки по новым правилам
        нужно явно применить её к заявке.
      </Notice>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <datalist id="context-fields"><option value="certificate_required" /><option value="gims_required" /><option value="project_type" /></datalist>
        <fieldset disabled={pending}>
          <label>
            Название программы
            <input
              required
              value={draft.name}
              onChange={(e) => change({ ...draft, name: e.target.value })}
            />
          </label>
          <div className="result-section">
            <div className="section-heading">
              <h3>Перечень документов</h3>
              <button
                type="button"
                className="button secondary compact"
                disabled={!types.data?.items.length}
                onClick={() =>
                  change({
                    ...draft,
                    requirements: [
                      ...draft.requirements,
                      {
                        document_type: types.data!.items[0].id,
                        kind: "optional",
                        id: crypto.randomUUID(), quantity: 1, needs_clarification: false,
                        predicate: null,
                        missing_severity: "info",
                      },
                    ],
                  })
                }
              >
                <Plus size={14} />
                Добавить документ
              </button>
            </div>
            {draft.requirements.map((req, index) => (
              <div className="requirement-editor" key={index}>
                <label>
                  Документ
                  <select
                    required
                    value={req.document_type}
                    onChange={(e) =>
                      change({
                        ...draft,
                        requirements: draft.requirements.map((r, i) =>
                          i === index
                            ? { ...r, document_type: e.target.value as typeof r.document_type }
                            : r,
                        ),
                      })
                    }
                  >
                    {types.data?.items.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.name}
                        {type.extension ? " · расширение" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Обязательность
                  <select
                    value={req.kind}
                    onChange={(e) => {
                      const kind = e.target.value as typeof req.kind;
                      change({
                        ...draft,
                        requirements: draft.requirements.map((r, i) =>
                          i === index
                            ? {
                                ...r,
                                kind,
                                missing_severity:
                                  kind === "conditional"
                                    ? "warning"
                                    : kind === "required"
                                      ? "error"
                                      : "info",
                                predicate:
                                  kind === "conditional"
                                    ? {
                                        field: "certificate_required",
                                        kind: "is_true",
                                      }
                                    : null,
                              }
                            : r,
                        ),
                      });
                    }}
                  >
                    <option value="required">Обязательный</option>
                    <option value="conditional">Условный</option>
                    <option value="optional">Дополнительный</option>
                  </select>
                </label>
                <label>
                  Количество
                  <input
                    type="number"
                    min="1"
                    step="1"
                    required
                    value={req.quantity}
                    onChange={(e) =>
                      change({
                        ...draft,
                        requirements: draft.requirements.map((r, i) =>
                          i === index
                            ? { ...r, quantity: Number(e.target.value) }
                            : r,
                        ),
                      })
                    }
                  />
                </label>
                {req.kind === "conditional" && <ConditionEditor value={req.predicate ?? null} onChange={predicate => change({ ...draft, requirements: draft.requirements.map((r, i) => i === index ? { ...r, predicate } : r) })} />}
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Удалить документ ${index + 1}`}
                  onClick={() =>
                    change({
                      ...draft,
                      requirements: draft.requirements.filter(
                        (_, i) => i !== index,
                      ),
                    })
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            <p className="form-hint">
              Условный дефицит всегда даёт замечание. Неизвестная применимость
              требует внимания.
            </p>
          </div>
          <div className="result-section">
            <div className="section-heading">
              <h3>Правила проверки</h3>
              <button
                type="button"
                className="button secondary compact"
                onClick={() =>
                  change({
                    ...draft,
                    rules: [
                      ...draft.rules,
                      {
                        id: crypto.randomUUID(),

                        family: "non_empty",
                        bindings: [],
                        parameters: {},
                        severity: "warning",

                        needs_clarification: true,
                      },
                    ],
                  })
                }
              >
                <Plus size={14} />
                Добавить правило
              </button>
            </div>
            {draft.rules.map((rule, index) => (
              <div className="rule-editor" key={index}>
                <div className="rule-editor-heading">
                  <strong>{rule.id}</strong>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Удалить правило ${rule.id}`}
                    onClick={() =>
                      change({
                        ...draft,
                        rules: draft.rules.filter((_, i) => i !== index),
                      })
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                <div className="form-grid">
                  <label>
                    Ключ правила
                    <input
                      required
                      value={rule.id}
                      onChange={(e) =>
                        changeRule(index, { ...rule, id: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Семейство
                    <select
                      value={rule.family}
                      onChange={(e) =>
                        changeRule(index, {
                          ...rule,
                          family: e.target.value as RuleDefinition["family"],
                          parameters: {},
                          needs_clarification: true,
                        })
                      }
                    >
                      {Object.entries(familyLabels).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Уровень замечания
                    <select
                      value={rule.severity}
                      onChange={(e) =>
                        changeRule(index, {
                          ...rule,
                          severity: e.target
                            .value as RuleDefinition["severity"],
                        })
                      }
                    >
                      <option value="error">Ошибка</option>
                      <option value="warning">Замечание</option>

                      <option value="info">Информация</option>
                    </select>
                  </label>
                  {parameterKeys[rule.family].map((key) => (
                    <label key={key}>
                      {parameterLabels[key]}
                      {key === "date_mode" ? <select required value={rule.parameters?.date_mode ?? ""} onChange={e => changeRule(index, { ...rule, parameters: { ...rule.parameters, date_mode: e.target.value as "not_future" | "not_expired" } })}><option value="">Выберите проверку</option><option value="not_future">Дата не в будущем</option><option value="not_expired">Срок не истёк</option></select> : <input
                        required
                        inputMode={key === "factor" ? "decimal" : "text"}
                        pattern={
                          key === "factor"
                            ? "0(\\.[0-9]+)?|1(\\.0+)?"
                            : undefined
                        }
                        value={key === "field_ids" ? (rule.parameters?.field_ids ?? []).join(", ") : key === "factor" ? rule.parameters?.factor ?? "" : key === "pattern" ? rule.parameters?.pattern ?? "" : rule.parameters?.date_mode ?? ""}
                        onChange={(e) =>
                          changeRule(index, {
                            ...rule,
                            parameters: {
                              ...rule.parameters,
                              [key]: key === "field_ids" ? e.target.value.split(",").map(v => v.trim()).filter(Boolean) : e.target.value,
                            },
                          })
                        }
                      />}</label>
                  ))}
                </div>
                <div className="binding-list">
                  <div className="section-heading">
                    <h4>Привязки полей</h4>
                    <button
                      type="button"
                      className="text-link"
                      disabled={!types.data?.items.length}
                      onClick={() =>
                        changeRule(index, {
                          ...rule,
                          bindings: [
                            ...(rule.bindings ?? []),
                            {
                              document_type: types.data!.items[0].id,
                              operand: `operand_${(rule.bindings ?? []).length + 1}`, field_id: "",
                              subject_role: "applicant",
                            },
                          ],
                        })
                      }
                    >
                      Добавить операнд
                    </button>
                  </div>
                  {(rule.bindings ?? []).map((binding, bindingIndex) => (
                    <div className="binding-row" key={bindingIndex}>
                      <label>Имя операнда<input required value={binding.operand} onChange={e => changeRule(index, { ...rule, bindings: (rule.bindings ?? []).map((b, i) => i === bindingIndex ? { ...b, operand: e.target.value } : b) })} /></label>
                      <label>
                        Вид
                        <select
                          value={binding.document_type}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              bindings: (rule.bindings ?? []).map((b, i) =>
                                i === bindingIndex
                                  ? { ...b, document_type: e.target.value as typeof b.document_type }
                                  : b,
                              ),
                            })
                          }
                        >
                          {types.data?.items.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Ключ поля
                        <input
                          required
                          value={binding.field_id}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              bindings: (rule.bindings ?? []).map((b, i) =>
                                i === bindingIndex
                                  ? { ...b, field_id: e.target.value }
                                  : b,
                              ),
                            })
                          }
                        />
                      </label>
                      <label>
                        Организация
                        <select
                          value={binding.subject_role ?? "unknown"}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              bindings: (rule.bindings ?? []).map((b, i) =>
                                i === bindingIndex
                                  ? {
                                      ...b,
                                      subject_role: (e.target.value ||
                                        "unknown") as typeof b.subject_role,
                                    }
                                  : b,
                              ),
                            })
                          }
                        >
                          <option value="unknown">Не указана</option>
                          <option value="person">Физическое лицо</option>
                          <option value="applicant">Заявитель</option>
                          <option value="guarantor">Гарант</option>
                        </select>
                      </label>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Удалить операнд ${bindingIndex + 1}`}
                        onClick={() =>
                          changeRule(index, {
                            ...rule,
                            bindings: (rule.bindings ?? []).filter(
                              (_, i) => i !== bindingIndex,
                            ),
                          })
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={rule.needs_clarification}
                    onChange={(e) =>
                      changeRule(index, {
                        ...rule,
                        needs_clarification: e.target.checked,
                      })
                    }
                  />
                  Параметры или привязка требуют уточнения
                </label>
                <p className="form-hint">
                  Отсутствующий операнд → «Не определено».{" "}
                  {rule.needs_clarification
                    ? "Неподтверждённое правило не может дать успешную проверку."
                    : ""}
                </p>
              </div>
            ))}
          </div>
        </fieldset>
        <ErrorNotice
          error={types.error || save.error || validate.error || publish.error}
        />
        {validate.data && (
          <>
            <Notice tone={validate.data.valid ? "success" : "warning"}>
              {validate.data.valid
                ? "Черновик прошёл серверную проверку."
                : "Сервер нашёл замечания. Исправьте черновик перед публикацией."}
            </Notice>
            <Issues issues={validate.data.issues} />
          </>
        )}
        <div className="form-actions">
          <button className="button secondary" disabled={pending || !dirty}>
            <Save size={16} />
            Сохранить черновик
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={pending || dirty || original.revision !== revision}
            onClick={() => validate.mutate()}
          >
            <Check size={16} />
            Проверить
          </button>
          <button
            type="button"
            className="button primary"
            disabled={
              pending || dirty || original.revision !== revision || validatedVersion !== draft.row_version
            }
            onClick={() => publish.mutate()}
          >
            <Send size={16} />
            Опубликовать редакцию
          </button>
        </div>
      </form>
    </section>
  );
}
export function AdminWorkspace() {
  const programs = useQuery({
    queryKey: ["programs"],
    queryFn: ({ signal }) => api.programs(signal),
  });
  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: ({ signal }) => api.drafts(signal),
  });
  const [programId, setProgramId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [draftId, setDraftId] = useState("");
  const versions = useQuery({
    queryKey: ["versions", programId],
    queryFn: ({ signal }) => api.versions(programId, signal),
    enabled: !!programId,
  });
  const selected = useQuery({
    queryKey: ["draft", draftId],
    queryFn: ({ signal }) => api.draft(draftId, signal),
    enabled: !!draftId,
  });
  const create = useCommand(
    () => api.createDraft(programs.data?.items.find(p => p.id === programId)?.name ?? "", versionId),
    (draft) => setDraftId(draft.id),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">РАБОЧЕЕ МЕСТО АДМИНИСТРАТОРА</span>
          <h1>Программы и правила</h1>
          <p>Настройте перечень документов, условия и параметры проверки.</p>
        </div>
        <Badge>Только администратор</Badge>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Новая редакция</h2>
          <span>На основе опубликованной версии</span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <div className="form-grid">
            <label>
              Программа
              <select
                required
                value={programId}
                onChange={(e) => {
                  setProgramId(e.target.value);
                  setVersionId("");
                }}
              >
                <option value="">Выберите программу</option>
                {programs.data?.items.map((program) => (
                  <option key={program.id} value={program.id}>
                    {program.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Исходная редакция
              <select
                required
                value={versionId}
                disabled={!programId}
                onChange={(e) => setVersionId(e.target.value)}
              >
                <option value="">Выберите редакцию</option>
                {versions.data?.items.map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ErrorNotice
            error={programs.error || versions.error || create.error}
          />
          <div className="form-actions">
            <button
              className="button secondary"
              disabled={create.isPending || !versionId}
            >
              <Plus size={16} />
              Создать черновик
            </button>
          </div>
        </form>
      </section>
      <section className="panel">
        <h2>Существующие черновики</h2>
        <ErrorNotice error={drafts.error} retry={() => void drafts.refetch()} />
        {drafts.isPending ? (
          <Loading />
        ) : !drafts.data?.items.length ? (
          <Empty title="Нет черновиков">
            Создайте редакцию на основе опубликованной программы.
          </Empty>
        ) : (
          <label>
            Выберите черновик
            <select
              value={draftId}
              onChange={(e) => setDraftId(e.target.value)}
            >
              <option value="">Выберите черновик</option>
              {drafts.data.items.map((draft) => (
                <option key={draft.id} value={draft.id}>
                  {draft.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>
      <ErrorNotice error={selected.error} />
      {draftId && selected.isPending && <Loading />}
      {selected.data && (
        <DraftEditor key={selected.data.id} original={selected.data} />
      )}
    </>
  );
}
