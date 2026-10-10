# Sber Case 3 — Агентство инноваций

Инструмент предварительной проверки пакетов документов на субсидию: определение видов документов, извлечение полей, проверка комплектности и правил. Окончательное решение принимает специалист.

Документация для реализации:

- [Спецификация архитектуры и инструкция по реализации](docs/specs.md) — основной документ для разработки.
- [Анализ кейса 3 и выбор стека](docs/case_3.md).
- [Коллаборация двух участников](docs/collaboration.md) — задачи, владельцы, контрольные точки и блокеры.
- [Сводка исходного положения и общих требований](docs/summary.md).

Репозиторий: [Bush-7th/sber-case3](https://github.com/Bush-7th/sber-case3).

## Фронтенд разработчика B

Реализован M14: React/TypeScript/Vite, TanStack Query, интерфейсы специалиста и администратора. Ветка `frontend/UI01`. Сервер/OpenAPI в текущем checkout отсутствуют; сквозная приёмка не выполнена. Фронтенд обращается к реальному `/api/v1`, без демонстрационных данных или fallback.

Для локальной разработки нужен Node.js ≥22.12:

В текущей Windows-среде для проверок установлен portable Node вне репозитория. Если `npm` отсутствует в PATH, в этой PowerShell-сессии можно выполнить:

```powershell
$env:PATH = "$env:LOCALAPPDATA\sber-case3-tools\node-v22.23.3-win-x64;" + $env:PATH
```

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Открыть `http://127.0.0.1:5173`. Dev proxy направляет `/api` на `http://127.0.0.1:8000`; адрес задаётся `API_PROXY_TARGET` в frontend/.env. Учётные записи создаёт backend A, тестовых логинов в рабочем приложении нет. Без API экран показывает ошибку подключения.

```powershell
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

Можно использовать установленный Edge вместо скачивания браузера: `$env:PLAYWRIGHT_CHANNEL='msedge'` перед `npm run test:e2e`. Playwright подменяет только HTTP-контракт; это не реальная приёмка документов. Docker из корня: `docker build -t sber-case3-web ./frontend`. Nginx ожидает `api:8000` в общей Docker-сети; Compose и серверные лимиты подключает A. В этой среде Docker не проверен.

Передача A: [контракт клиента](docs/frontend-contract.md), [каталог](catalogs/README.md). Материалы B: [тестовая матрица](docs/test-matrix.md), [архитектура](docs/architecture.md), [решения](docs/decisions.md), [локальная модель](docs/local-model.md), [ограничения](docs/limitations.md), [ИИ-отчёт](docs/ai-usage.md), [сценарий защиты](docs/demo.md).
