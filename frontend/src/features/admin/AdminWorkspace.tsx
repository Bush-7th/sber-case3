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
  required_fields: ["fields"],
  non_empty: [],
  matches_regex: ["pattern"],
  date_compare: ["operator", "reference"],
  ratio_gte: ["factor"],
  amount_equal: [],
  same_subject_value: ["subject_role"],
};
const parameterLabels: Record<string, string> = {
  fields: "Поля (через запятую)",
  pattern: "Шаблон полного совпадения",
  operator: "Операция сравнения",
  reference: "Дата сравнения",
  factor: "Минимальная доля (0.50 = 50%)",
  subject_role: "Роль организации",
};

function DraftEditor({ original }: { original: ProgramDraft }) {
  const [draft, setDraft] = useState(original);
  const [dirty, setDirty] = useState(false);
  const [validatedVersion, setValidatedVersion] = useState<number | null>(null);
  const [published, setPublished] = useState("");
  const types = useQuery({
    queryKey: ["document-types"],
    queryFn: ({ signal }) => api.documentTypes(signal),
  });
  const save = useCommand(
    () => api.saveDraft(draft),
    (saved) => {
      setDraft(saved);
      setDirty(false);
      setValidatedVersion(null);
    },
  );
  const validate = useCommand(
    () => api.validateDraft(draft),
    (result) => setValidatedVersion(result.valid ? draft.row_version : null),
  );
  const publish = useCommand(
    () => api.publishDraft(draft),
    (version) => setPublished(version.label),
  );
  const pending = save.isPending || validate.isPending || publish.isPending;
  function change(next: ProgramDraft) {
    setDraft(next);
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
      {original.row_version > draft.row_version && (
        <Notice tone="warning">
          Черновик изменён другим участником. Сверьте введённые данные перед
          загрузкой новой версии.
          <button
            type="button"
            className="button secondary compact"
            onClick={() => {
              setDraft(original);
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
                        count: 1,
                        predicate: null,
                        severity: "info",
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
                            ? { ...r, document_type: e.target.value }
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
                                severity:
                                  kind === "conditional"
                                    ? "warning"
                                    : kind === "required"
                                      ? "error"
                                      : "info",
                                predicate:
                                  kind === "conditional"
                                    ? {
                                        field: "certificate_required",
                                        operator: "is_true",
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
                    value={req.count}
                    onChange={(e) =>
                      change({
                        ...draft,
                        requirements: draft.requirements.map((r, i) =>
                          i === index
                            ? { ...r, count: Number(e.target.value) }
                            : r,
                        ),
                      })
                    }
                  />
                </label>
                {req.kind === "conditional" && (
                  <label>
                    Условие
                    <select
                      value={req.predicate?.field ?? "certificate_required"}
                      onChange={(e) =>
                        change({
                          ...draft,
                          requirements: draft.requirements.map((r, i) =>
                            i === index
                              ? {
                                  ...r,
                                  predicate: {
                                    field: e.target.value as
                                      | "certificate_required"
                                      | "gims_required",
                                    operator: "is_true",
                                  },
                                }
                              : r,
                          ),
                        })
                      }
                    >
                      <option value="certificate_required">
                        Нужен сертификат = да
                      </option>
                      <option value="gims_required">Нужна ГИМС = да</option>
                    </select>
                  </label>
                )}
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
                        name: "Новое правило",
                        family: "non_empty",
                        operands: [],
                        parameters: {},
                        severity: "attention",
                        on_missing: "UNKNOWN",
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
              <div className="rule-editor" key={rule.id}>
                <div className="rule-editor-heading">
                  <strong>{rule.name}</strong>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Удалить правило ${rule.name}`}
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
                    Название
                    <input
                      required
                      value={rule.name}
                      onChange={(e) =>
                        changeRule(index, { ...rule, name: e.target.value })
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
                      <option value="attention">Требует внимания</option>
                      <option value="info">Информация</option>
                    </select>
                  </label>
                  {parameterKeys[rule.family].map((key) => (
                    <label key={key}>
                      {parameterLabels[key]}
                      <input
                        required
                        inputMode={key === "factor" ? "decimal" : "text"}
                        pattern={
                          key === "factor"
                            ? "0(\\.[0-9]+)?|1(\\.0+)?"
                            : undefined
                        }
                        value={rule.parameters[key] ?? ""}
                        onChange={(e) =>
                          changeRule(index, {
                            ...rule,
                            parameters: {
                              ...rule.parameters,
                              [key]: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
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
                          operands: [
                            ...rule.operands,
                            {
                              document_type: types.data!.items[0].id,
                              field: "",
                              subject_role: "applicant",
                            },
                          ],
                        })
                      }
                    >
                      Добавить операнд
                    </button>
                  </div>
                  {rule.operands.map((binding, bindingIndex) => (
                    <div className="binding-row" key={bindingIndex}>
                      <label>
                        Вид
                        <select
                          value={binding.document_type}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              operands: rule.operands.map((b, i) =>
                                i === bindingIndex
                                  ? { ...b, document_type: e.target.value }
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
                          value={binding.field}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              operands: rule.operands.map((b, i) =>
                                i === bindingIndex
                                  ? { ...b, field: e.target.value }
                                  : b,
                              ),
                            })
                          }
                        />
                      </label>
                      <label>
                        Организация
                        <select
                          value={binding.subject_role ?? ""}
                          onChange={(e) =>
                            changeRule(index, {
                              ...rule,
                              operands: rule.operands.map((b, i) =>
                                i === bindingIndex
                                  ? {
                                      ...b,
                                      subject_role: (e.target.value ||
                                        null) as typeof b.subject_role,
                                    }
                                  : b,
                              ),
                            })
                          }
                        >
                          <option value="">Не указана</option>
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
                            operands: rule.operands.filter(
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
            disabled={pending || dirty}
            onClick={() => validate.mutate()}
          >
            <Check size={16} />
            Проверить
          </button>
          <button
            type="button"
            className="button primary"
            disabled={
              pending || dirty || validatedVersion !== draft.row_version
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
    () => api.createDraft(programId, versionId),
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
