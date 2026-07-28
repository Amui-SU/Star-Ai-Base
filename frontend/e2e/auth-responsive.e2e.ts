import { expect, test, type Page } from "@playwright/test";

function collectRuntimeErrors(page: Page) {
  const errors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      if (message.location().url.endsWith("/system-auth/me")) return;
      errors.push(`${message.location().url || "inline"}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));

  return errors;
}

async function prepareLoggedOutPage(page: Page) {
  await page.route("**/favicon.ico", (route) =>
    route.fulfill({ status: 204, body: "" }),
  );
  await page.route("http://127.0.0.1:8000/system-auth/me", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Not authenticated" }),
    }),
  );
}

test("keeps the desktop account hint below the login card", async ({
  page,
}, testInfo) => {
  const runtimeErrors = collectRuntimeErrors(page);
  await prepareLoggedOutPage(page);
  await page.setViewportSize({ width: 2048, height: 1152 });
  await page.goto("/");

  await expect(page).toHaveTitle("智库云 - 收藏夹知识库");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();

  const card = page.locator(".auth-card");
  const hint = page.locator(".auth-account-hint");
  await expect
    .poll(async () => {
      const [currentCard, currentHint] = await Promise.all([
        card.boundingBox(),
        hint.boundingBox(),
      ]);
      if (!currentCard || !currentHint) return Number.NEGATIVE_INFINITY;
      return currentHint.y - (currentCard.y + currentCard.height);
    })
    .toBeGreaterThanOrEqual(0);

  const [cardBox, hintBox] = await Promise.all([
    card.boundingBox(),
    hint.boundingBox(),
  ]);

  expect(cardBox).not.toBeNull();
  expect(hintBox).not.toBeNull();
  expect(hintBox!.y).toBeGreaterThanOrEqual(cardBox!.y + cardBox!.height);
  expect(
    Math.abs(
      hintBox!.x + hintBox!.width / 2 - (cardBox!.x + cardBox!.width / 2),
    ),
  ).toBeLessThanOrEqual(2);

  const offsets = await page.evaluate(() => ({
    brandX: new DOMMatrix(
      getComputedStyle(document.querySelector(".auth-brand")!).transform,
    ).e,
    formY: new DOMMatrix(
      getComputedStyle(document.querySelector(".auth-form-section-lowered")!)
        .transform,
    ).f,
  }));
  expect(offsets).toEqual({ brandX: -16, formY: -24 });

  const email = page.getByPlaceholder("输入邮箱地址");
  await email.fill("reader@example.com");
  await expect(email).toHaveValue("reader@example.com");
  expect(runtimeErrors).toEqual([]);
  const desktopScreenshot = testInfo.outputPath("desktop-login.png");
  await page.screenshot({ path: desktopScreenshot });
  await testInfo.attach("desktop-login", {
    path: desktopScreenshot,
    contentType: "image/png",
  });
});

test("keeps the mobile login page inside the viewport", async ({
  page,
}, testInfo) => {
  const runtimeErrors = collectRuntimeErrors(page);
  await prepareLoggedOutPage(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await expect(page.locator(".auth-form-content")).toHaveCSS("opacity", "1");
  await expect(page.locator(".auth-account-hint")).toBeVisible();

  const layout = await page.evaluate(() => {
    const brand = document.querySelector(".auth-brand")!;
    const form = document.querySelector(".auth-form-section-lowered")!;
    return {
      brandX: new DOMMatrix(getComputedStyle(brand).transform).e,
      formY: new DOMMatrix(getComputedStyle(form).transform).f,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    };
  });

  expect(layout.brandX).toBe(0);
  expect(layout.formY).toBe(0);
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth);
  expect(runtimeErrors).toEqual([]);
  const mobileScreenshot = testInfo.outputPath("mobile-login.png");
  await page.screenshot({ path: mobileScreenshot });
  await testInfo.attach("mobile-login", {
    path: mobileScreenshot,
    contentType: "image/png",
  });
});
