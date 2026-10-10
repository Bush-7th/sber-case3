import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { ProjectContext } from "../../shared/api/contracts";
import { ErrorNotice } from "../../shared/ui";

export const initialContext: ProjectContext = {
  project_type: "",
  certificate_required: "unknown",
  gims_required: "unknown",
  conditions: {},
};
export function ProgramFields({
  programId,
  versionId,
  context,
  onProgram,
  onVersion,
  onContext,
  locked = false,
}: {
  programId: string;
  versionId: string;
  context: ProjectContext;
  onProgram?: (id: string) => void;
  onVersion: (id: string) => void;
  onContext: (context: ProjectContext) => void;
  locked?: boolean;
}) {
  const programs = useQuery({
    queryKey: ["programs"],
    queryFn: ({ signal }) => api.programs(signal),
  });
  const versions = useQuery({
    queryKey: ["versions", programId],
    queryFn: ({ signal }) => api.versions(programId, signal),
    enabled: !!programId,
  });
  return (
    <>
      <div className="form-grid">
        <label>
          Программа
          <select
            required
            value={programId}
            disabled={!onProgram || locked}
            onChange={(e) => onProgram?.(e.target.value)}
          >
            <option value="">Выберите программу</option>
            {programs.data?.items.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Редакция правил
          <select
            required
            value={versionId}
            disabled={!programId || locked}
            onChange={(e) => onVersion(e.target.value)}
          >
            <option value="">Выберите редакцию</option>
            {versions.data?.items.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Тип проекта
          <input
            value={context.project_type}
            disabled={locked}
            onChange={(e) =>
              onContext({ ...context, project_type: e.target.value })
            }
            placeholder="Укажите, если известен"
          />
        </label>
        {(["certificate_required", "gims_required"] as const).map((key) => (
          <label key={key}>
            {key === "certificate_required"
              ? "Нужен сертификат?"
              : "Нужна декларация ГИМС?"}
            <select
              value={context[key]}
              disabled={locked}
              onChange={(e) =>
                onContext({
                  ...context,
                  [key]: e.target.value as ProjectContext[typeof key],
                })
              }
            >
              <option value="unknown">Пока неизвестно</option>
              <option value="true">Да</option>
              <option value="false">Нет</option>
            </select>
          </label>
        ))}
      </div>
      <p className="form-hint">
        Неизвестное условие требует внимания. Отсутствие условного документа
        показывается как замечание.
      </p>
      <ErrorNotice error={programs.error || versions.error} />
    </>
  );
}
