# CON01 — контракт API и TypeScript-клиент

Источник истины — [Pydantic DTO](../backend/src/app/http_api/schemas.py) и [объявления маршрутов](../backend/src/app/http_api/routes.py). FastAPI экспортирует [OpenAPI](../backend/openapi.json); из него генерируются [типы TypeScript](../frontend/src/shared/api/schema.ts). JSON и сгенерированный TypeScript вручную не редактируются.

## 1. Готовность текущего этапа

Объявлены 25 операций ядра `/api/v1` из specs §9: сессии, программы/версии, заявки/загрузка/перепроверка, результаты, исходники/превью/таблицы, тип/группировка, решение, административные черновики/правила/публикация и аудит. `GET /admin/program-drafts/{draft_id}` возвращает полный черновик, PATCH коллекции не используется: изменяется конкретный черновик по ID.

INF01 реализует вход/выход и серверную проверку сессии, роли, CSRF/Origin. Без сессии защищённый запрос получает **401 session_required**, без нужной роли/CSRF — **403 access_denied**. После разрешения доступа неподключённый прикладной обработчик получает **501 not_implemented**, некорректное тело — **422 invalid_command**. Сервер пока не принимает документы и не выполняет распознавание. Доступны `/openapi.json`, `/docs` и две диагностические операции `/health/live`, `/health/ready`; OpenAPI 0.2.0 содержит 25 операций ядра и 2 health. Настройка БД, bootstrap, область прав и результаты проверок — в [runtime.md](runtime.md). Результаты контрактных тестов не означают приёмку бизнес-сценариев.

## 2. Данные и состояния

- ID ресурсов/версий/запусков/отчётов — UUID. ID правила/поля/слота — строковый ключ каталога. Входная ревизия `input_revision` и прогресс `progress_version` независимы; счётчики неотрицательны.
- Десятичные значения — строки без экспоненты и запятой, например `"0.50"`. Числа JS не используются для денежных полей. Нормализованные даты полей — `YYYY-MM-DD`, timestamp — ISO со смещением. Дата/таймзона проверки фиксируются в запуске/отчёте.
- `ProjectContext.conditions` принимает true/false/null; null означает неизвестное условие. Поле `project_type` отдельно. Отсутствующий/нечитаемый/конфликтующий машинный факт имеет `normalized: null`, а известный — значение и источник. Ручная правка чисел не входит в контракт ядра.
- Файл имеет `processing` и отдельный `processing_stage`: preparing/ocr/extracting/validating либо null до начала. Запуск, покрытие, актуальность, машинный verdict и решение человека — отдельные поля. Решение accepted/needs_revision/rejected не является автоматическим pass.
- `MachineReport` содержит basis=machine, ревизии, версию программы, правила/комплектность/замечания, дату и источники. PASS запрещён при partial/provisional, неразрешённых проверках или замечаниях. Отсутствующий условный документ остаётся warning, обязательный — error.
- `PackageSummary` явно передаёт актуальность/предварительность отчёта и актуальность решения; UI не должен отображать старое принятие как решение по новой ревизии. `FileSummary.page_count`/`sheet_names` позволяют построить просмотрщик после подготовки; до неё число страниц неизвестно.
- SourceLocation — различимые page/sheet/paragraph. Page: исходник/версия, номер с 1, необязательные preview ID и bbox. Bbox нормирован к указанной странице, задаётся только при проверенных координатах. Sheet: имя листа и диапазон A1. Paragraph: путь блока/таблицы. EvidenceRef содержит фрагмент и native/ocr/vision; OCR обязательно ссылается на сохранённый OcrResult.
- Программы имеют опубликованные неизменяемые версии; черновик — собственную revision. Предикаты ограничены equals/is_true/all/any, семейства правил — семью операциями из specs. Параметр factor — десятичная строка. Проверка ссылок/bindings и исполнимости определения относится к CAT01/RUL01.

## 3. Команды и транспорт

Смысловые правки заявки, повтор проверки, тип/группа и решение передают `expected_revision` в JSON. Для admin-команд это ожидаемая revision черновика. У загрузки поле находится в multipart рядом со списком `files`; границу формирует HTTP-клиент. Если ничего не принято, сервер сохраняет ревизию и не создаёт пустой run.

`Idempotency-Key` — непрозрачная строка 1–128 символов, обязательная для загрузки, явного повторного запуска, решения и публикации программы. Повтор того же содержимого имеет один эффект; тот же ключ с другим содержимым — 409. Реальная обработка конфликтов/ключей появится вместе с прикладными сервисами. Клиент автоматически не повторяет команды.

Сессия использует серверную cookie `session`: HttpOnly, SameSite=Strict, Path=/api/v1, настраиваемый Secure и срок. Секрет сессии и CSRF хранятся хешированными; выход отзывает запись. Все изменения после входа требуют `X-CSRF-Token`, полученный вместе с SessionResponse. Cookie и CSRF в OpenAPI — совместные требования. Административные операции имеют tag administrator и требуют серверной роли administrator; обычный специалист их выполнить не может. Проверка конкретного владельца остаётся обязательной при подключении прикладного ресурса в INT01/REV01.

Единая ошибка: code/message/details/correlation_id. ID корреляции — UUID, также в `X-Correlation-ID`. Валидационные ошибки включают loc/type, без отражения входных значений, паролей или содержимого документов. В FileCheck ошибка дополнительно связывается с processing_stage. APIError клиента сохраняет HTTP status, code, details и correlationId; HTML/неструктурированная ошибка прокси заменяется понятным сообщением.

Списки программ/версий/заявок/черновиков/аудита: items/total/offset/limit, начальный limit 20, максимум 100. Ячейки: offset/limit, начальный limit 200, максимум 1000. Исходник — двоичный ответ с attachment, preview — PDF/PNG, необязательный page query с 1; клиент читает их как Blob. Фактические содержимое/авторизацию реализует M03/INF01.

## 4. Генерация и использование

Требуются Python 3.12–3.13, uv, Node версии из `frontend/.node-version` и npm. Зависимости закреплены в uv.lock/package-lock.json.

```bash
uv sync --project backend --locked
uv run --project backend python -m app.http_api.export_openapi
cd frontend
npm ci
npm run api:generate
npm run api:check
npm run typecheck
npm test
```

Backend-проверки из корня: `uv run --project backend pytest` и `uv run --project backend ruff check backend/src backend/tests`. Проверка свежести JSON: `uv run --project backend python -m app.http_api.export_openapi --check`. Экспорт запускает сборку контрактного приложения без БД, модели и credentials.

Клиент [createApiClient](../frontend/src/shared/api/openapi-client.ts), экспортируемый через `shared/api/index.ts`, предоставляет `http` со всеми типизированными операциями, uploadFiles и Blob-методы. Экраны переведены на него через `client.ts`; `adapters.ts` преобразует DTO CON01 в локальные модели и проверяет ответы Zod. Полный admin definition сохраняется без перевода в предварительную схему. `getCsrfToken` читает актуальный токен состояния сессии; секрет cookie и ключи OCR/Qwen клиенту не передаются. Для same-origin запросов использовать общий origin или dev-прокси; начальный вход не требует предыдущего CSRF-токена. Виды документов читаются из definition редакции; восстановление сессии остаётся ограничением INF01.

`npm test` запускает обе группы транспортных тестов: Vitest для текущего UI-адаптера и Node/tsx для клиента CON01. `npm run typecheck` проверяет SPA и отдельно контрактный клиент с `noUncheckedIndexedAccess`/`exactOptionalPropertyTypes`. TypeScript закреплён на версии 5.9.3 для совместимости генератора `openapi-typescript`; Vite/React-зависимости сохранены.

```typescript
import { createApiClient } from "./shared/api/index.js";

let csrfToken: string | undefined;
const api = createApiClient({ getCsrfToken: () => csrfToken });
const login = await api.http.POST("/api/v1/sessions", {
  body: { username, password },
});
csrfToken = login.data?.csrf_token;
await api.http.POST("/api/v1/packages/{package_id}/verification-runs", {
  params: { path: { package_id: packageId }, header: { "Idempotency-Key": requestKey } },
  body: { expected_revision: revision },
});
```

Вход в примере работает после миграций/bootstrap; запрос проверки пока отвечает 501. После правки DTO/маршрутов A обновляет OpenAPI, B регенерирует клиент и проверяет потребителей; изменение фиксируется в [collaboration.md](collaboration.md) до реализации UI.
