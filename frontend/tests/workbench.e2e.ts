import { test, expect, type Page } from "@playwright/test";
import type { components } from "../src/shared/api/schema";
import { draft, errorBody, file, ids, item, pageOf, program, requested, run, session, timestamp, version } from "./fixtures";
type S = components["schemas"];

async function install(page: Page, role: "specialist" | "administrator" = "specialist") {
  const state = { item: structuredClone(item), run: structuredClone(run), draft: structuredClone(draft), authenticated: false };
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path === "/api/v1/sessions" && route.request().method() === "POST") { state.authenticated = true; body = { ...session, user: { ...session.user, role } }; }
    else if (path === "/api/v1/sessions" && route.request().method() === "GET") {
      if (!state.authenticated) { await route.fulfill({ status: 401, json: errorBody("session_required") }); return; }
      body = { ...session, user: { ...session.user, role } };
    }
    else if (path === "/api/v1/sessions" && route.request().method() === "DELETE") { state.authenticated = false; await route.fulfill({ status: 204 }); return; }
    else if (path === "/api/v1/programs") body = pageOf([program]);
    else if (path === `/api/v1/programs/${ids.program}/versions`) body = pageOf([version]);
    else if (path === "/api/v1/packages") body = route.request().method() === "POST" ? state.item : pageOf([state.item]);
    else if (path === `/api/v1/packages/${ids.package}`) body = state.item;
    else if (path === `/api/v1/verification-runs/${ids.run}`) body = state.run;
    else if (path === `/api/v1/packages/${ids.package}/audit`) body = pageOf([]);
    else if (path === "/api/v1/admin/program-drafts") body = pageOf([state.draft]);
    else if (path === `/api/v1/admin/program-drafts/${ids.draft}`) body = state.draft;
    else if (path === `/api/v1/files/${ids.file}/preview`) { await route.fulfill({ contentType: "text/plain", body: "Контрактное превью" }); return; }
    else { await route.fulfill({ status: 404, json: errorBody("not_found") }); return; }
    await route.fulfill({ json: body });
  });
  return state;
}
async function login(page: Page, target = "/packages") {
  await page.goto(target);
  await page.getByLabel("Логин", { exact: true }).fill("specialist");
  await page.getByLabel("Пароль", { exact: true }).fill("test-password");
  await page.getByLabel("Пароль", { exact: true }).press("Enter");
  await expect(page.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
}
async function workspace(page: Page) {
  await login(page);
  await page.getByRole("link", { name: item.title }).click();
  await expect(page.getByText(/Предварительный результат:/)).toBeVisible();
}
async function confirmDecision(page: Page) {
  await page.getByPlaceholder("Зафиксируйте, на чём основано ваше решение").fill("Проверены исходные документы");
  await page.getByRole("checkbox", { name: /Я проверил/ }).check();
}
function decisionResponse(body: S["DecisionCreate"]): S["ApplicationDecision"] {
  return { id: ids.document, package_id: ids.package, input_revision: body.expected_revision, report_id: body.report_id ?? null, action: body.action, reason: body.reason, author: session.user, decided_at: timestamp, freshness: "current" };
}

test("reload restores the session, navigation and CSRF for logout", async ({ page }) => {
  await install(page); await login(page);
  await page.reload();
  await expect(page.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: item.title })).toBeVisible();
  await page.route("**/api/v1/sessions", async route => {
    if (route.request().method() !== "DELETE") { await route.fallback(); return; }
    expect(route.request().headers()["x-csrf-token"]).toBe(session.csrf_token);
    await route.fulfill({ status: 204 });
  });
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
});

test("specialist redirects from admin and sees separate assessments", async ({ page }) => {
  await install(page); await login(page, "/admin");
  await expect(page).toHaveURL(/\/packages$/);
  await expect(page.getByRole("link", { name: "Программы и правила" })).toHaveCount(0);
  await expect(page.getByRole("columnheader", { name: "Автоматическая проверка" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Решение специалиста" })).toBeVisible();
});
test("partial report preserves UNKNOWN and conditional/optional severities", async ({ page }) => {
  await install(page); await workspace(page);
  await expect(page.getByText("Не определено", { exact: true })).toBeVisible();
  await expect(page.locator(".requirement-row").filter({ hasText: "Сертификат" }).locator(".badge")).toHaveClass(/warning/);
  await expect(page.locator(".requirement-row").filter({ hasText: "Дополнительная презентация" }).locator(".badge")).toHaveClass(/info/);
  await expect(page.getByRole("button", { name: "Зафиксировать решение" })).toBeDisabled();
  let command: S["DecisionCreate"] | undefined;
  await page.route(`**/packages/${ids.package}/decisions`, async route => {
    command = route.request().postDataJSON();
    expect(route.request().headers()["x-csrf-token"]).toBe(session.csrf_token);
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    await route.fulfill({ json: decisionResponse(command!) });
  });
  await confirmDecision(page); await page.getByRole("button", { name: "Зафиксировать решение" }).click();
  await expect.poll(() => command?.expected_revision).toBe(2); expect(command?.report_id).toBe(ids.report); expect(command).not.toHaveProperty("verdict");
});
test("session expiry removes protected data", async ({ page }) => {
  await install(page); await login(page);
  await expect(page.getByRole("heading", { name: "Заявки", exact: true })).toBeVisible();
  await page.route("**/api/v1/packages?*", route => route.fulfill({ status: 401, json: errorBody("session_required") }));
  await expect(page.getByRole("heading", { name: "Вход в систему" })).toBeVisible({ timeout: 8000 });
  await expect(page.getByText(item.title)).toHaveCount(0);
});
test("server outage shows a retry without a successful data result", async ({ page }) => {
  await install(page); await login(page);
  await page.route("**/api/v1/packages?*", route => route.fulfill({ status: 503, json: errorBody("dependency_unavailable") }));
  await expect(page.getByRole("alert")).toContainText("Сервис временно недоступен", { timeout: 8000 });
  await expect(page.getByRole("button", { name: "Повторить", exact: true })).toBeVisible();
});
test("admin saves 60 percent preserving full definition and validates before publishing", async ({ page }) => {
  const state = await install(page, "administrator");
  await page.route("**/api/v1/admin/program-drafts/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/validate")) { expect(route.request().postDataJSON()).toEqual({ expected_revision: 2 }); await route.fulfill({ json: { draft_id: ids.draft, revision: 2, valid: true, issues: [], correlation_id: ids.correlation } }); return; }
    if (path.endsWith("/publish")) { expect(route.request().headers()["idempotency-key"]).toBeTruthy(); await route.fulfill({ json: { ...version, version: 2 } }); return; }
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      expect(Object.keys(body).sort()).toEqual(["definition", "expected_revision"]);
      expect(body.expected_revision).toBe(1);
      expect(body.definition.requirements[1].predicate).toEqual(draft.definition.requirements[1].predicate);
      expect(body.definition.document_types).toEqual(draft.definition.document_types);
      expect(body.definition.rules[0].bindings).toEqual(draft.definition.rules[0].bindings);
      state.draft = { ...state.draft, definition: body.definition, revision: 2 };
    }
    await route.fulfill({ json: state.draft });
  });
  await login(page); await page.getByLabel("Выберите черновик").selectOption(ids.draft);
  const publish = page.getByRole("button", { name: "Опубликовать редакцию" }); await expect(publish).toBeDisabled();
  await page.getByLabel("Минимальная доля (0.50 = 50%)").fill("0.60");
  await page.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(page.getByText(/версия изменений 2/)).toBeVisible(); expect(state.draft.definition.rules[0].parameters?.factor).toBe("0.60");
  await page.getByRole("button", { name: "Проверить", exact: true }).click(); await expect(publish).toBeEnabled(); await publish.click();
  await expect(page.getByText(/Редакция «Редакция 2» опубликована/)).toBeVisible();
});
test("desktop and phone lists have no page overflow", async ({ page }) => {
  await install(page); await login(page);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { name: "Заявки", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});
test("expired session after reload returns to login and clears protected data", async ({ page }) => {
  const state = await install(page);
  const requests: string[] = []; page.on("request", request => requests.push(`${request.method()} ${new URL(request.url()).pathname}`));
  await login(page); state.authenticated = false; await page.reload();
  await expect(page.getByRole("heading", { name: "Вход в систему" })).toBeVisible();
  expect(requests).toContain("GET /api/v1/sessions");
  await expect(page.getByText(item.title)).toHaveCount(0);
});
test("configuration recovers after 409 only after explicit revision review", async ({ page }) => {
  const state = await install(page); await workspace(page);
  await page.getByRole("button", { name: "Настройки заявки" }).click();
  await page.getByLabel("Тип проекта", { exact: true }).fill("Локальная правка");
  const revisions: number[] = [];
  await page.route(`**/packages/${ids.package}/configuration`, async route => {
    revisions.push(route.request().postDataJSON().expected_revision);
    if (revisions.length === 1) { state.item.input_revision = 3; await route.fulfill({ status: 409, json: errorBody("revision_conflict") }); }
    else await route.fulfill({ json: { ...requested, input_revision: 4 } });
  });
  await page.getByRole("button", { name: "Применить и перепроверить" }).click();
  await expect(page.getByRole("button", { name: "Применить и перепроверить" })).toBeDisabled();
  await page.getByRole("button", { name: "Сверено: применить правки к актуальной ревизии" }).click();
  await expect(page.getByLabel("Тип проекта", { exact: true })).toHaveValue("Локальная правка");
  await page.getByRole("button", { name: "Применить и перепроверить" }).click();
  await expect.poll(() => revisions).toEqual([2, 3]);
});
test("decision preserves reason and requires revision adoption after 409", async ({ page }) => {
  const state = await install(page); await workspace(page);
  const revisions: number[] = [];
  await page.route(`**/packages/${ids.package}/decisions`, async route => {
    const body = route.request().postDataJSON(); revisions.push(body.expected_revision);
    if (revisions.length === 1) { state.item.input_revision = 3; await route.fulfill({ status: 409, json: errorBody("revision_conflict") }); }
    else await route.fulfill({ json: decisionResponse(body) });
  });
  await confirmDecision(page); await page.getByRole("button", { name: "Зафиксировать решение" }).click();
  await page.getByRole("button", { name: "Сверено: использовать актуальную ревизию" }).click();
  await expect(page.getByPlaceholder("Зафиксируйте, на чём основано ваше решение")).toHaveValue("Проверены исходные документы");
  await expect(page.getByRole("checkbox", { name: /Я проверил/ })).not.toBeChecked();
  await page.getByRole("checkbox", { name: /Я проверил/ }).check(); await page.getByRole("button", { name: "Зафиксировать решение" }).click();
  await expect.poll(() => revisions).toEqual([2, 3]);
});
test("a report update invalidates human confirmation", async ({ page }) => {
  const state = await install(page); state.run.status = "running";
  await workspace(page); await confirmDecision(page);
  state.run.progress_version = 2; state.run.report!.id = ids.document;
  await expect(page.getByRole("checkbox", { name: /Я проверил/ })).not.toBeChecked({ timeout: 8000 });
  await expect(page.getByRole("button", { name: "Зафиксировать решение" })).toBeDisabled();
  await expect(page.getByText(/Отчёт или ревизия изменились/)).toBeVisible();
});
test("an ambiguous decision retry keeps body and key while the report changes", async ({ page }) => {
  const state = await install(page); state.run.status = "running";
  await workspace(page); const commands: unknown[] = []; const keys: string[] = [];
  await page.route(`**/packages/${ids.package}/decisions`, async route => {
    const body = route.request().postDataJSON(); commands.push(body); keys.push(route.request().headers()["idempotency-key"]);
    if (commands.length === 1) { state.run.progress_version = 2; state.run.report!.id = ids.document; await route.abort("failed"); }
    else await route.fulfill({ json: decisionResponse(body) });
  });
  await confirmDecision(page); await page.getByRole("button", { name: "Зафиксировать решение" }).click();
  const retry = page.getByRole("button", { name: "Повторить сохранение решения" }); await expect(retry).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /Я проверил/ })).not.toBeChecked({ timeout: 8000 });
  await retry.click(); await expect.poll(() => commands.length).toBe(2);
  expect(commands[0]).toEqual(commands[1]); expect(keys[0]).toBe(keys[1]); expect(commands[1]).toMatchObject({ report_id: ids.report });
});
test("duplicate filenames cannot cause accepted documents to be resubmitted", async ({ page }) => {
  await install(page); await workspace(page);
  // Empty buffers test selection/transport only and are never sent to an OCR service.
  await page.locator('input[type="file"]').setInputFiles([{ name: "same.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(0) }, { name: "same.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(1) }]);
  await expect(page.locator(".selected-files li")).toHaveCount(1);
  await expect(page.getByText(/Файлы с совпадающими именами не добавлены/)).toBeVisible();
  await page.route(`**/packages/${ids.package}/files`, route => route.fulfill({ json: { ...requested, accepted: [{ ...file, original_name: "same.pdf" }], rejected: [] } }));
  await page.getByRole("button", { name: "Загрузить и проверить" }).click();
  await expect(page.locator(".selected-files li")).toHaveCount(0);
});
test("sources open by file ID and grouping sends fragment IDs", async ({ page }) => {
  await install(page); await workspace(page);
  await page.getByRole("button", { name: "Источник 1" }).click();
  await expect(page.locator(".document-frame")).toHaveAttribute("src", `/api/v1/files/${ids.file}/preview?page=2`);
  await expect(page.getByText("Извлечено из изображения")).toBeVisible();
  let command: unknown;
  await page.route(`**/document-units/${ids.document}/grouping`, async route => { command = route.request().postDataJSON(); await route.fulfill({ json: requested }); });
  await page.getByRole("button", { name: "Исправить тип / состав" }).click();
  await page.getByPlaceholder("Почему меняете тип или состав документа").fill("Подтверждена страница");
  await page.getByRole("button", { name: "Подтвердить состав" }).click();
  await expect.poll(() => command).toEqual({ expected_revision: 2, fragment_ids: [ids.fragment], reason: "Подтверждена страница" });
});
test("stale report and human decision are visibly stale in the list", async ({ page }) => {
  const state = await install(page); state.item.report_freshness = "outdated"; state.item.decision_status = "accepted"; state.item.decision_freshness = "outdated";
  await login(page);
  await expect(page.getByText("Принята · устарело")).toBeVisible();
  await expect(page.getByText("Требует внимания · устарел")).toBeVisible();
});
test("spreadsheets use explicit sheet names and paginate cells", async ({ page }) => {
  const state = await install(page); const spreadsheet = { ...file, format: "xlsx" as const, sheet_names: ["Первый", "Расчёт"] };
  state.item.files = [spreadsheet]; state.run.files![0].file = spreadsheet;
  const requests: string[] = [];
  await page.route(`**/files/${ids.file}/sheets/**`, async route => {
    const url = new URL(route.request().url()); requests.push(url.pathname + url.search);
    const offset = Number(url.searchParams.get("offset"));
    await route.fulfill({ json: { file_id: ids.file, file_version_id: ids.fileVersion, sheet: decodeURIComponent(url.pathname.split("/").at(-1)!), offset, limit: 200, total: 2, cells: [{ address: offset === 0 ? "A1" : "A2", value: offset === 0 ? false : "123.45", formula: null, known_state: "known" }] } });
  });
  await workspace(page); await expect(page.getByRole("cell", { name: "false", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Загрузить ещё ячейки" }).click();
  await expect(page.getByRole("cell", { name: "123.45", exact: true })).toBeVisible();
  await page.getByLabel("Лист", { exact: true }).selectOption("Расчёт");
  await expect.poll(() => requests.some(url => decodeURIComponent(url).includes("/Расчёт?"))).toBe(true);
  expect(requests.every(url => !url.includes("_first"))).toBe(true);
});
