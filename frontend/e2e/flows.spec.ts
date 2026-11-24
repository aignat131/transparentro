import { expect, test } from "@playwright/test";

// Fluxul 1: cetățeanul caută o firmă și ajunge la profilul ei.
test("căutare → profil firmă → contract", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("banii publici");
  // primul furnizor din lista de firme, căutat după nume fără diacritice
  await page.goto("/firme");
  const first = page.locator("main ul li a").first();
  const name = (await first.textContent())!.trim();
  const word = name.split(/\s+/).find((w) => w.length > 3 && !/persoan/i.test(w)) ?? name.split(" ")[0];

  await page.goto("/cautare");
  const box = page.getByRole("searchbox", { name: /caută o instituție/i }).first();
  await box.fill(word);
  await box.press("Enter");
  await expect(page).toHaveURL(/\/cautare\?q=/);
  const firms = page.getByRole("region", { name: "Firme" });
  await expect(firms.getByRole("link").first()).toBeVisible();
  await firms.getByRole("link").first().click();
  await expect(page).toHaveURL(/\/firme\//);
  await expect(page.getByRole("heading", { name: /Contracte cu statul, pe ani/ })).toBeVisible();

  // din profilul firmei, un contract
  await page.getByTestId("contract-table").getByRole("link").first().click();
  await expect(page).toHaveURL(/\/contracte\/\d+/);
  await expect(page.getByRole("heading", { name: "Tot ce se știe despre contract" })).toBeVisible();
  await expect(page.getByText("Sursa oficială")).toBeVisible();
});

// Fluxul 2: profilul unei instituții: grafice, top furnizori, glosar (tooltip), contracte.
test("instituție → top furnizori → glosar → contract", async ({ page }) => {
  await page.goto("/institutii");
  await page.locator("main ul li a").first().click();
  await expect(page).toHaveURL(/\/institutii\/\d+/);
  await expect(page.getByRole("heading", { name: "Top 10 furnizori" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Pe ce s-au cheltuit banii/ })).toBeVisible();
  // tooltip de glosar accesibil
  const term = page.getByRole("button", { name: /Ce înseamnă: Achiziție directă/ }).first();
  await term.click();
  await expect(page.getByRole("tooltip")).toContainText("prag");
  await page.keyboard.press("Escape");
  await page.getByTestId("contract-table").getByRole("link").first().click();
  await expect(page).toHaveURL(/\/contracte\/\d+/);
});

// Fluxul 3: filtrarea contractelor și semnalele.
test("filtre contracte și semnale", async ({ page }) => {
  await page.goto("/contracte");
  const count = page.getByTestId("result-count");
  const toNum = (t: string | null) => Number((t ?? "0").trim().split(" ")[0].replace(/\./g, ""));
  const before = toNum(await count.textContent());
  await page.getByLabel("Valoare minimă (lei)").fill("100000");
  await page.getByLabel("Ordonare").selectOption("value_desc");
  await page.getByRole("button", { name: "Aplică filtrele" }).click();
  await expect(page).toHaveURL(/min_value=100000/);
  const after = toNum(await count.textContent());
  expect(after).toBeLessThanOrEqual(before);
  const values = await page.getByTestId("contract-table").locator("tbody tr td:last-child").allTextContents();
  const nums = values.map((v) => Number(v.replace(/[^\d,]/g, "").replace(",", ".")));
  expect(nums.every((n) => n >= 100000)).toBeTruthy();
  expect([...nums].sort((a, b) => b - a)).toEqual(nums);

  await page.goto("/semnale");
  await expect(page.getByText("Nu sunt acuzații", { exact: false }).first()).toBeVisible();
  const cards = page.getByTestId("signal-card");
  if ((await cards.count()) > 0) {
    await expect(cards.first()).toContainText("Scor");
  }
});

test("pagini statice și SEO", async ({ page, request }) => {
  for (const p of ["/metodologie", "/surse-de-date", "/despre", "/disclaimer", "/glosar", "/harta"]) {
    const r = await page.goto(p);
    expect(r?.status(), p).toBe(200);
  }
  const sm = await request.get("/sitemap.xml");
  expect(sm.ok()).toBeTruthy();
  expect(await sm.text()).toContain("/institutii/");
  const og = await request.get("/opengraph-image");
  expect(og.headers()["content-type"]).toContain("image/png");
});

// Secțiunea ONG-uri: pagina se încarcă, cu selector de an și cele două tabele.
test("pagina ONG-uri", async ({ page }) => {
  await page.goto("/ong");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ONG-uri");
  await expect(page.getByRole("navigation", { name: "Alege anul" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /ONG-urile care au primit/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /ONG-urile care au cumpărat/ })).toBeVisible();
});
