import { expect, test, type Page } from "@playwright/test";

// HTTP contract tests only. These DTOs are not recognition results or real document acceptance.
const session = {
  user: { id: "test-user", name: "Тестовый специалист", role: "specialist" },
  csrf_token: "test-csrf",
};
const program = {
  id: "innovation",
  name: "Инновационный проект",
  description: "Программа",
};
const pageOf = (items: unknown[]) => ({ items, next_cursor: null });
const file = {
  id: "file-1",
  name: "Исходный файл.pdf",
  format: "pdf",
  size_bytes: 2048,
  processing: "checked",
  processing_stage: "validating",
  verdict: "review_required",
  error: null,
};
const item = {
  id: "pkg-1",
  title: "Заявка для проверки интерфейса",
  program_id: "innovation",
  program_name: program.name,
  program_version_id: "v1",
  input_revision: 2,
  updated_at: "2026-10-10T10:00:00Z",
  file_count: 1,
  verdict: "review_required",
  decision: null,
  context: {
    project_type: "",
    certificate_required: "unknown",
    gims_required: "unknown",
  },
  files: [file],
  requested_run_id: "run-1",
  decisions: [],
  report_history: [],
};
const run = {
  id: "run-1",
  input_revision: 2,
  progress_version: 1,
  status: "completed",
  coverage: "partial",
  freshness: "current",
  provisional: true,
  progress: { accepted: 1, running: 0, terminal: 1 },
  files: [file],
  document_units: [],
  report: {
    id: "report-1",
    basis: "machine",
    verdict: "review_required",
    issues: [],
    requirements: [
      {
        document_type: "certificate",
        kind: "conditional",
        status: "missing",
        message: "Сертификат не найден",
      },
    ],
    rules: [
      {
        id: "amount",
        name: "Согласованность суммы",
        status: "UNKNOWN",
        explanation: "Запрашиваемая сумма не найдена в обосновании.",
        sources: [],
      },
    ],
  },
  provider: null,
};

async function setup(page: Page, role = "specialist") {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path === "/api/v1/sessions")
      body = { ...session, user: { ...session.user, role } };
    else if (path === "/api/v1/programs") body = pageOf([program]);
    else if (path === "/api/v1/programs/innovation/versions")
      body = pageOf([
        { id: "v1", label: "Редакция 1", published_at: "2026-10-10T10:00:00Z" },
      ]);
    else if (path === "/api/v1/document-types")
      body = pageOf([
        { id: "application", name: "Заявление", extension: false },
      ]);
    else if (path === "/api/v1/packages")
      body = route.request().method() === "POST" ? item : pageOf([item]);
    else if (path === "/api/v1/packages/pkg-1") body = item;
    else if (path === "/api/v1/verification-runs/run-1") body = run;
    else if (path === "/api/v1/packages/pkg-1/audit") body = pageOf([]);
    else if (path === "/api/v1/files/file-1/preview") {
      await route.fulfill({
        contentType: "text/plain",
        body: "Превью в контрактном тесте",
      });
      return;
    } else {
      await route.fulfill({ status: 404, json: { code: "NOT_FOUND" } });
      return;
    }
    await route.fulfill({ json: body });
  });
}

test("specialist is redirected away from admin and sees separate assessments", async ({
  page,
}) => {
  await setup(page);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/packages$/);
  await expect(
    page.getByRole("link", { name: "Программы и правила" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("columnheader", { name: "Автоматическая проверка" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Решение специалиста" }),
  ).toBeVisible();
});

test("partial report shows unknown, conditional warning and explicit human decision", async ({
  page,
}, testInfo) => {
  await setup(page);
  await page.goto("/packages/pkg-1");
  await expect(page.getByText(/Предварительный результат:/)).toBeVisible();
  await expect(page.getByText("Не определено", { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("workspace.png"),
    fullPage: true,
  });
  const requirement = page.locator(".requirement-row");
  await expect(requirement.locator(".badge")).toHaveClass(/warning/);
  await expect(
    page.getByRole("button", { name: "Зафиксировать решение" }),
  ).toBeDisabled();
  await page
    .getByPlaceholder("Зафиксируйте, на чём основано ваше решение")
    .fill("Проверены исходные документы");
  await page.getByRole("checkbox", { name: /Я проверил/ }).check();
  await expect(
    page.getByRole("button", { name: "Зафиксировать решение" }),
  ).toBeEnabled();
  let command: Record<string, unknown> | undefined;
  await page.route("**/packages/pkg-1/decisions", async (route) => {
    command = route.request().postDataJSON();
    expect(route.request().headers()["x-csrf-token"]).toBe("test-csrf");
    await route.fulfill({
      json: {
        id: "decision-1",
        action: command!.action,
        reason: command!.reason,
        author: session.user.name,
        created_at: "2026-10-10T11:00:00Z",
        input_revision: 2,
        report_id: "report-1",
      },
    });
  });
  await page.getByRole("button", { name: "Зафиксировать решение" }).click();
  await expect.poll(() => command?.expected_revision).toBe(2);
  expect(command).not.toHaveProperty("verdict");
});

test("session expiry hides protected data", async ({ page }) => {
  await setup(page);
  await page.goto("/packages");
  await expect(
    page.getByRole("heading", { name: "Заявки", exact: true }),
  ).toBeVisible();
  await page.route("**/api/v1/packages?*", (route) =>
    route.fulfill({ status: 401, json: { code: "SESSION_EXPIRED" } }),
  );
  await expect(
    page.getByRole("heading", { name: "Вход в систему" }),
  ).toBeVisible({ timeout: 8000 });
  await expect(page.getByText(item.title)).toHaveCount(0);
});

test("server outage never becomes a successful session", async ({ page }) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 503, json: { code: "DEPENDENCY_FAILURE" } }),
  );
  await page.goto("/packages");
  await expect(page.getByRole("alert")).toContainText(
    "Сервис временно недоступен",
  );
  await expect(page.getByRole("button", { name: "Повторить" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Заявки", exact: true }),
  ).toHaveCount(0);
});

test("admin saves 60 percent and publishes only after server validation", async ({
  page,
}) => {
  await setup(page, "admin");
  let draft = {
    id: "draft-1",
    program_id: "innovation",
    name: program.name,
    row_version: 1,
    requirements: [
      {
        document_type: "application",
        kind: "required",
        count: 1,
        predicate: null,
        severity: "error",
      },
    ],
    rules: [
      {
        id: "ratio",
        name: "Доля средств",
        family: "ratio_gte",
        operands: [
          {
            document_type: "application",
            field: "own_funds",
            subject_role: "applicant",
          },
        ],
        parameters: { factor: "0.50" },
        severity: "error",
        on_missing: "UNKNOWN",
        needs_clarification: false,
      },
    ],
  };
  await page.route("**/api/v1/admin/program-drafts**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/validate")) {
      await route.fulfill({ json: { valid: true, issues: [] } });
      return;
    }
    if (path.endsWith("/publish")) {
      await route.fulfill({
        json: {
          id: "v2",
          label: "Редакция 2",
          published_at: "2026-10-10T11:00:00Z",
        },
      });
      return;
    }
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      expect(body.expected_row_version).toBe(1);
      draft = { ...draft, ...body, row_version: 2 };
    }
    await route.fulfill({
      json: path.endsWith("/draft-1") ? draft : pageOf([draft]),
    });
  });
  await page.goto("/admin");
  await page.getByLabel("Выберите черновик").selectOption("draft-1");
  const publish = page.getByRole("button", { name: "Опубликовать редакцию" });
  await expect(publish).toBeDisabled();
  await page.getByLabel("Минимальная доля (0.50 = 50%)").fill("0.60");
  await page.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(page.getByText(/версия изменений 2/)).toBeVisible();
  expect(draft.rules[0].parameters.factor).toBe("0.60");
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(publish).toBeEnabled();
  await publish.click();
  await expect(
    page.getByText(/Редакция «Редакция 2» опубликована/),
  ).toBeVisible();
});

test("layouts have no page overflow at desktop and phone widths", async ({
  page,
}, testInfo) => {
  await setup(page);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/packages");
    await expect(
      page.getByRole("heading", { name: "Заявки", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`list-${width}.png`),
      fullPage: true,
    });
  }
});

test("login works with keyboard and leaves no protected content before authentication", async ({
  page,
}, testInfo) => {
  await setup(page);
  let authenticated = false;
  await page.route("**/api/v1/sessions", async (route) => {
    if (route.request().method() === "POST") authenticated = true;
    await route.fulfill(
      authenticated
        ? { json: {
            user: { id: session.user.id, display_name: session.user.name, role: "specialist" },
            csrf_token: session.csrf_token,
            expires_at: "2026-10-10T20:00:00Z",
          } }
        : { status: 401, json: { code: "UNAUTHORIZED" } },
    );
  });
  await page.goto("/packages");
  await expect(
    page.getByRole("heading", { name: "Вход в систему" }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("login.png"),
    fullPage: true,
  });
  await page.getByLabel("Логин").fill("specialist");
  await page.getByLabel("Пароль").fill("test-password");
  await page.getByLabel("Пароль").press("Enter");
  await expect(
    page.getByRole("heading", { name: "Заявки", exact: true }),
  ).toBeVisible();
});
