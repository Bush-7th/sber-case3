import type { ReactNode } from "react";
import { AlertCircle, FileSearch, RefreshCw } from "lucide-react";
import { ApiError } from "../api/client";
import type { Issue } from "../api/contracts";

export const verdictLabels = {
  pass: "Пройден",
  review_required: "Требует внимания",
  issues: "Есть ошибки",
};
export const decisionLabels = {
  accepted: "Принята",
  needs_revision: "На доработке",
  rejected: "Отклонена",
};
export const stageLabels = {
  preparing: "Подготовка",
  ocr: "Распознавание текста",
  extracting: "Извлечение полей",
  validating: "Проверка данных",
};
const messages: Record<string, string> = {
  NETWORK_ERROR:
    "Не удалось связаться с сервером. Проверьте подключение и повторите действие.",
  CONTRACT_MISMATCH:
    "Ответ сервера не соответствует ожидаемому формату. Нужна сверка версии приложения с API.",
  INVALID_RESPONSE: "Сервер вернул ответ, который не удалось прочитать.",
  OCR_EMPTY:
    "Распознавание не нашло текст. Проверьте читаемость исходного файла.",
  OCR_TIMEOUT: "Распознавание текста заняло слишком много времени.",
  OCR_UNAVAILABLE: "Сервис распознавания текста временно недоступен.",
  OCR_UNAUTHORIZED:
    "Не удалось подключиться к распознаванию текста. Администратору нужно проверить доступ.",
  MODEL_TIMEOUT:
    "Извлечение полей заняло слишком много времени. Сохранённый текст остаётся доступен.",
  PROVIDER_UNAVAILABLE: "Сервис извлечения полей временно недоступен.",
  INVALID_MODEL_OUTPUT:
    "Ответ модели не прошёл проверку. Найденные значения нельзя использовать.",
  UNSUPPORTED_FORMAT:
    "Формат файла не поддерживается. Допустимы PDF, DOC, DOCX, XLS, XLSX, JPG и PNG.",
  FILE_TOO_LARGE: "Файл превышает установленный сервером размер.",
};
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Сессия закончилась. Войдите снова.";
    if (error.status === 403)
      return "У вашей учётной записи нет доступа к этому действию.";
    if (error.status === 409)
      return "Данные уже изменились. Актуальная версия загружена; проверьте изменения перед повтором.";
    if (error.status === 413)
      return "Загрузка превышает ограничение сервера. Уменьшите пакет.";
    if (error.status === 422)
      return "Сервер отклонил данные формы. Проверьте заполненные поля.";
    if (error.status === 503)
      return "Сервис временно недоступен. Повторите позже.";
    return (
      messages[error.code] ||
      "Действие не выполнено. Повторите позже или обратитесь к администратору."
    );
  }
  return "Не удалось выполнить действие. Повторите попытку.";
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={18} />
      <div>
        {errorMessage(error)}
        {error instanceof ApiError && error.correlationId && (
          <small>Номер обращения: {error.correlationId}</small>
        )}
      </div>
      {retry && (
        <button className="button secondary compact" onClick={retry}>
          <RefreshCw size={14} />
          Повторить
        </button>
      )}
    </div>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <div className={`notice ${tone}`}>
      <AlertCircle size={18} />
      <div>{children}</div>
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span className={`badge ${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <FileSearch size={30} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      Загрузка данных…
    </div>
  );
}
export function dateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? "Дата неизвестна"
    : date.toLocaleString("ru-RU", {
        timeZone: "Europe/Moscow",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function bytes(size: number) {
  return size < 1024 * 1024
    ? `${Math.ceil(size / 1024)} КБ`
    : `${(size / 1024 / 1024).toFixed(1)} МБ`;
}
export function fileCount(count: number) {
  const tail = count % 100;
  const last = count % 10;
  return `${count} ${tail >= 11 && tail <= 14 ? "файлов" : last === 1 ? "файл" : last >= 2 && last <= 4 ? "файла" : "файлов"}`;
}
export function Issues({ issues }: { issues: Issue[] }) {
  return (
    <div className="issue-list">
      {issues.map((issue, i) => (
        <div key={`${issue.code}-${i}`} className={`issue ${issue.severity}`}>
          <Badge tone={issue.severity}>
            {
              {
                error: "Ошибка",
                warning: "Замечание",
                attention: "Внимание",
                info: "Информация",
              }[issue.severity]
            }
          </Badge>
          <p>{issue.message}</p>
        </div>
      ))}
    </div>
  );
}
