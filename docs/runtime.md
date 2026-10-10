# INF01 — инфраструктура и доступ

Реализованы SQLAlchemy/UoW, миграция Alembic, bytea BlobStore, серверные сессии двух ролей, проверка CSRF/Origin и liveness/readiness. Конфигурация находится в [Settings](../backend/src/app/runtime/settings.py), сборка — в [AppContainer](../backend/src/app/runtime/container.py), запуск — в [compose.yaml](../compose.yaml).

## Запуск Docker Compose

Нужны Docker Engine с доступом текущего пользователя к daemon и Docker Compose. Команды выполняются из корня репозитория.

1. Скопировать `.env.example` в `.env`.
2. Задать собственные `POSTGRES_PASSWORD`, `BOOTSTRAP_SPECIALIST_PASSWORD` и `BOOTSTRAP_ADMIN_PASSWORD`. Пароли пользователей должны иметь не менее 12 символов. `.env` исключён из Git.
3. Оставить `MODEL_PROVIDER=local` для инфраструктурного прогона: настройки и ключ внешнего Qwen не требуются.
4. Проверить конфигурацию и запустить API:

```bash
docker compose config --quiet
docker compose up --build -d api
docker compose ps -a
curl --fail http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

Порядок запуска: healthcheck PostgreSQL → миграции → создание двух пользователей → API. Provisioning-команды завершаются, API продолжает работать. Повтор bootstrap не меняет существующие пароли/роли и не активирует отключённого пользователя. Новые пароли в `.env` сами по себе не являются командой смены пароля. Изменение пароля PostgreSQL в `.env` также не меняет пароль уже созданной БД в volume.

API опубликован только на `127.0.0.1:8000`; PostgreSQL и Ollama не публикуют порты. Исходники в bytea и сессии находятся в постоянном `postgres-data`. Для остановки с сохранением данных:

```bash
docker compose down
docker compose up --build -d api
```

Не добавлять `--volumes` к остановке, если данные нужны. Ollama подключается отдельным профилем, с постоянным `ollama-data` и явной загрузкой модели:

```bash
docker compose --profile local up -d ollama
docker compose --profile local exec ollama ollama pull qwen3-vl:2b-instruct
```

Образы Python 3.13.5, PostgreSQL 17.11 и Ollama 0.12.10 закреплены тегами и digest; их наличие в официальном registry проверено. LOC01 проверила реальный CPU-анализ: 2B выбрана начальным локальным профилем после сравнения с 4B. Настройки, инструкции и ограничения — в [local-model.md](local-model.md). Docker-прогон по-прежнему требует доступа к daemon. Отдельный worker/долговечная очередь подключаются в INT01, frontend-сервис — в UI01, изолированный Office-конвертер — в FMT01. В API-контейнере нет OCR-весов или LibreOffice.

## Сессии и права

`POST /api/v1/sessions` принимает username/password и возвращает UserSummary, срок и CSRF-токен. Пароли хешируются Argon2id. Cookie `session` содержит случайный 256-битный секрет; PostgreSQL хранит только SHA-256 секрета и CSRF-токена, срок и отзыв. Cookie имеет HttpOnly, SameSite=Strict, Path=/api/v1, Max-Age. Для HTTPS включить `SESSION_COOKIE_SECURE=true`; production отвергает false.

Все защищённые запросы разрешаются через серверную сессию до чтения JSON/multipart. Все POST/PATCH/DELETE/PUT после входа требуют `X-CSRF-Token`. Origin проверяется по `ALLOWED_ORIGINS`; cross-site запросы отвергаются и при входе. CLI без Origin может использовать API. Для frontend предполагается общий origin или Vite-прокси; CORS не включён.

| Действие | Специалист | Администратор |
| --- | --- | --- |
| Вход/выход, чтение опубликованного каталога | Разрешено | Разрешено |
| Заявки, проверки, документы, решение | Разрешено для собственных ресурсов | Запрещено |
| Административные черновики и правила | Запрещено | Разрешено |

Проверка владельца принимает ResourceAccess от модуля, владеющего ресурсом; Identity не читает таблицы заявок. До INT01/REV01 прикладные операции и выдача исходников отвечают 501 после разрешённого доступа. Они не возвращают данные без проверки владельца. Ключи модели и OCR доступны только серверным процессам; пароль bootstrap передаётся только одноразовому bootstrap-сервису.

`DELETE /api/v1/sessions` с действующим CSRF отзывает запись в БД и удаляет cookie с теми же флагами. Старый секрет после выхода, истечения срока или отключения пользователя получает 401. Сессии переживают перезапуск API.

## Хранилище и эксплуатация

PostgresBlobStore реализует `put_immutable/head/open/delete_unreferenced`, а также удержание/освобождение ссылки на ресурс. Повтор того же ID и содержимого возвращает прежний BlobRef; другое содержимое или media type дают BlobConflict. Конкурентный повтор не перезаписывает байты. `head` не загружает содержимое. Ссылки и GC сериализуются блокировкой строки; удерживаемый blob удалить нельзя. Это внутренний порт; HTTP-контроллер сначала проверяет доступ к файлу, затем открывает байты.

OCR01 добавляет миграцию `0002_ocr_results`: версии оригиналов и сохранённый OCR с производной страницей/профилем. Повтор `migrate` применяет её поверх INF01; работа с отдельным OCR-клиентом и результаты реального прогона описаны в [ocr.md](ocr.md). QWN01 добавляет отдельную фабрику/CLI модели, nullable-схемы и проверку источников по [qwen.md](qwen.md). Миграция БД и публичные endpoints в QWN01/LOC01 не менялись. LOC01 добавляет общий выбор провайдера, локальный CLI и подготовку ограниченных изображений; источник пока должен быть сохранён от OCR01. Общая готовность pipeline по-прежнему ожидает остальные адаптеры и INT01.

Blob и ссылки используют UoW вызывающего сценария; изменения сохраняются только после явного commit. Необработанный выход или исключение откатывают изменения. Байты, размер и SHA-256 сохраняются вместе; БД проверяет фактическую длину bytea. Внешнее object storage можно подключить через тот же порт на следующем этапе.

`/health/live` возвращает 200, пока обслуживаются HTTP-запросы, независимо от модели/БД. `/health/ready` проверяет БД, актуальность схемы и наличие активных пользователей двух ролей. Сейчас он возвращает 503 `not_ready`: details.api_ready может быть true, но details.pipeline_ready=false, а каталог/модель/конвертер отмечены not_checked. Наличие контейнера или успешный `/health` провайдера не считается реальным анализом. Позднее OCR01/QWN01/LOC01/FMT01/INT01 добавят фактическую готовность своих адаптеров. Health polling не вызывает удалённые модели.

Ошибки сохраняют ApiError и correlation ID. События HTTP пишутся JSON: метод, статус, correlation_id; для неожиданного сбоя — класс ошибки. Логи не содержат URL с параметрами, тела документов, пароли, cookie или исключения драйвера. В Compose access log Uvicorn отключён.

## Локальная разработка и проверки

Для запуска Python вне Docker указать `DATABASE_URL` с драйвером `postgresql+psycopg` или `DB_HOST/DB_PORT/POSTGRES_*` для доступного PostgreSQL, затем:

```bash
uv sync --project backend --locked
uv run --project backend python -m app.runtime.cli migrate
uv run --project backend python -m app.runtime.cli bootstrap
uv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Контракты/документация экспортируются без БД и ключей. При отсутствии конфигурации БД сервер может показать Swagger и liveness, но защищённые операции не принимаются. Неизвестный профиль или неполная внешняя конфигурация останавливают runtime с безопасным сообщением.

```bash
uv run --project backend pytest
uv run --project backend ruff check backend/src backend/tests backend/migrations
uv run --project backend python -m app.http_api.export_openapi --check
```

Для интеграционных тестов задать `TEST_DATABASE_URL` на PostgreSQL с правом CREATE DATABASE. Тесты создают отдельную случайно названную БД, выполняют миграции, проверяют API/bytea и удаляют только собственную БД; указанная разработчиком БД не очищается. Без этой настройки integration-проверки явно пропускаются.

**Проверено 10.10.2026:** 37 backend-тестов прошли, включая настоящий PostgreSQL 17.11, upgrade/downgrade и сравнение metadata, роли/прямые URL, CSRF/Origin/TLS-cookie, безопасные ошибки/логи, отзыв/expiry/отключение, повтор bootstrap, перезапуск API, rollback/retention и конкурентный повтор blob. Использованы in-memory байты хранилища, без синтетических документов и модельных заглушек вместо реальных вызовов.

5 тестов клиента, TypeScript typecheck, Ruff check/format и свежесть OpenAPI/типов проверены. Установка закреплённых runtime-зависимостей без dev прошла в отдельной чистой среде. Compose config и переменные окружения провалидированы. Полный build/up и сохранность Docker volumes после пересоздания контейнеров ещё не проверены: текущий пользователь не имеет доступа к `/var/run/docker.sock`, sudo требует пароль. INF01 остаётся на проверке; следующий совместный прогон должен закрыть именно эти проверки. Доступные прямые прогоны PostgreSQL не заменяют проверку контейнеров.
