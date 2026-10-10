# Sber Case 3 — Агентство инноваций

Инструмент предварительной проверки пакетов документов на субсидию: определение видов документов, извлечение полей, проверка комплектности и правил. Окончательное решение принимает специалист.

Документация для реализации:

- [Спецификация архитектуры и инструкция по реализации](docs/specs.md) — основной документ для разработки.
- [Анализ кейса 3 и выбор стека](docs/case_3.md).
- [Коллаборация двух участников](docs/collaboration.md) — задачи, владельцы, контрольные точки и блокеры.
- [Контракт API и типизированный клиент](docs/api-contract.md) — этап CON01, генерация и проверки.
- [Инфраструктура и запуск](docs/runtime.md) — этап INF01, Compose, миграции, сессии и проверки.
- [Удалённый OCR](docs/ocr.md) — этап OCR01, подготовка страниц, сохранение текста и реальный прогон.
- [Qwen и извлечение](docs/qwen.md) — этап QWN01, проверенное подключение, схемы/источники и реальный прогон.
- [Сводка исходного положения и общих требований](docs/summary.md).

Репозиторий: [Bush-7th/sber-case3](https://github.com/Bush-7th/sber-case3).

## Фронтенд разработчика B

Реализован M14: React/TypeScript/Vite, TanStack Query, интерфейсы специалиста и администратора. Ветка `frontend/UI01`. Из main объединены CON01/INF01/OCR01/QWN01. Все экраны используют типизированный клиент `openapi-client.ts` через `client.ts/adapters.ts` и DTO CON01. Вход и выход работают с реальным API; прикладные обработчики пока отвечают 501, сквозная приёмка документов не выполнена.

Для локальной разработки нужен Node.js 24 (точная версия — `frontend/.node-version`):

В текущей Windows-среде для проверок установлен portable Node вне репозитория. Если `npm` отсутствует в PATH, в этой PowerShell-сессии можно выполнить:

```powershell
$env:PATH = "$env:LOCALAPPDATA\sber-case3-tools\node-v24.21.0-win-x64;" + $env:PATH
```

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Открыть `http://127.0.0.1:5173`. Dev proxy направляет `/api` на `http://127.0.0.1:8000`; адрес задаётся `API_PROXY_TARGET` в frontend/.env. Учётные записи создаёт backend A, тестовых логинов в рабочем приложении нет. Без API экран показывает ошибку подключения.

Для текущего локального просмотра в Windows запущены Vite на `127.0.0.1:5173`, API в WSL на `127.0.0.1:18802` и отдельная PostgreSQL проекта. Адрес API записан в игнорируемом `frontend/.env`. Созданы `specialist` и `administrator`; их случайные локальные пароли находятся в `BOOTSTRAP_SPECIALIST_PASSWORD` / `BOOTSTRAP_ADMIN_PASSWORD` корневого `.env`. Вход и выход используют настоящие серверные сессии. Список заявок и административные операции пока показывают недоступность функции (501).

```powershell
npm run build
npm run typecheck
npm run api:check
npm test
npx playwright install chromium
npm run test:e2e
```

Можно использовать установленный Edge вместо скачивания браузера: `$env:PLAYWRIGHT_CHANNEL='msedge'` перед `npm run test:e2e`. Playwright подменяет только HTTP-контракт; это не реальная приёмка документов. Docker из корня: `docker build -t sber-case3-web ./frontend`. Nginx ожидает `api:8000` в общей Docker-сети; Compose и серверные лимиты подключает A. В этой среде Docker не проверен.

Передача A: [контракт клиента](docs/frontend-contract.md), [каталог](catalogs/README.md). Материалы B: [тестовая матрица](docs/test-matrix.md), [архитектура](docs/architecture.md), [решения](docs/decisions.md), [локальная модель](docs/local-model.md), [ограничения](docs/limitations.md), [ИИ-отчёт](docs/ai-usage.md), [сценарий защиты](docs/demo.md).

## Backend CON01 / INF01 / OCR01 / QWN01

Вход и выход подключены к INF01: запрос передаёт username/password, ответ display_name/administrator преобразуется в модель интерфейса. GET `/sessions` отсутствует: после обновления страницы нужно войти снова. Виды документов читаются из definition конкретной редакции/черновика. Заявки, каталог и обработка документов пока отвечают `501 not_implemented`; конечные DTO UI проверены контрактными тестами, реальная приёмка остаётся впереди.

Подготовлены Pydantic/OpenAPI, TypeScript-клиент, отдельные OCR/Qwen-адаптеры и инфраструктура INF01: миграции PostgreSQL, bytea-хранилище, сессии и серверные права. Малые реальные OCR/Qwen-вызовы проверены отдельными CLI. Обработка документов через API и прикладные операции пока возвращают `501 not_implemented` после проверки доступа. Полный Docker-прогон ещё требует проверки; фактические результаты записаны в инструкции запуска.

Контрактный API для разработки (Python 3.12–3.13 и uv):

```bash
uv sync --project backend --locked
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Без настроек БД доступны документация и `/health/live`; вход требует миграций и bootstrap по [инструкции](docs/runtime.md). Схема: `http://127.0.0.1:8000/openapi.json`, Swagger: `http://127.0.0.1:8000/docs`. Подготовка Node, генерация клиента и проверки описаны в документе контракта.
