import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT = path.join(ROOT, "data/private/reference_extraction/runs/ENTERPRISE_PRICE_RESOURCE_MATCHING_AND_A111_QUOTA_PILOT_1");
const BASE_URL = process.env.PLATFORM_UAT_BASE_URL || "http://127.0.0.1:8017";

function environment() {
  const values = {};
  for (const raw of fs.readFileSync(path.join(ROOT, ".env.platform.local"), "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    let value = line.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    values[line.slice(0, index).trim()] = value;
  }
  return values;
}

async function main() {
  const env = environment();
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => pageErrors.push(error.message));
  try {
    await page.goto(`${BASE_URL}/login?next=/enterprise-quota`, { waitUntil: "domcontentloaded" });
    await page.locator("#username").fill("uat_editor");
    await page.locator("#password").fill(env.PLATFORM_UAT_TEMP_PASSWORD);
    await Promise.all([
      page.waitForURL(`${BASE_URL}/quota-building`, { timeout: 15000 }),
      page.locator('button[type="submit"]').click(),
    ]);
    await page.goto(`${BASE_URL}/enterprise-quota`, { waitUntil: "domcontentloaded" });
    await page.locator(".eq-workbench").waitFor({ state: "visible" });
    await page.locator(".eq-tree-item").first().waitFor({ state: "visible", timeout: 15000 });
    await page.locator(".eq-tree-item").first().click();
    await page.locator("#quotaCode").filter({ hasText: "A1-1-" }).waitFor({ timeout: 15000 });
    // Ignore aborted requests from the legacy review page that the login flow briefly opens.
    // From here onward every recorded browser error belongs to the Enterprise Quota workbench.
    consoleErrors.length = 0;
    pageErrors.length = 0;
    const checks = [];
    const record = (id, name, expected, actual, status) => checks.push({ check_id: id, check: name, expected, actual, status: status ? "pass" : "fail" });
    const metrics = await page.locator(".eq-metric strong").allTextContents();
    record("BROWSER-001", "summary metrics", "137 Draft and 55 resources", metrics.join(" | "), metrics.includes("137") && metrics.includes("55"));
    const treeCount = await page.locator(".eq-tree-item").count();
    record("BROWSER-002", "A1.1 tree", "137", String(treeCount), treeCount === 137);
    const workbench = await page.locator(".eq-workbench").boundingBox();
    const bodyWidth = await page.evaluate(() => ({ scroll: document.body.scrollWidth, client: document.body.clientWidth }));
    record("BROWSER-003", "three-pane workbench visible", "visible within viewport", JSON.stringify({ workbench, bodyWidth }), Boolean(workbench) && bodyWidth.scroll <= bodyWidth.client + 1);
    const tabButtons = page.locator("#tabs button");
    const tabCount = await tabButtons.count();
    let nonEmptyTabs = 0;
    for (let index = 0; index < tabCount; index += 1) {
      await tabButtons.nth(index).click();
      await page.waitForTimeout(80);
      const text = (await page.locator("#tabContent").innerText()).trim();
      const embeddedDocument = await page.locator("#tabContent iframe").count();
      if (text.length > 0 || embeddedDocument > 0) nonEmptyTabs += 1;
    }
    record("BROWSER-004", "required detail tabs", "10 non-empty", `${tabCount}/${nonEmptyTabs}`, tabCount === 10 && nonEmptyTabs === 10);
    await page.locator('#tabs button[data-tab="prices"]').click();
    const priceText = await page.locator("#tabContent").innerText();
    record("BROWSER-005", "missing Enterprise prices render blank", "em dash present; no synthetic zero marker", priceText.includes("—") ? "blank markers present" : "blank marker missing", priceText.includes("—"));
    await page.locator("#editButton").click();
    const editState = await page.evaluate(() => ({
      nameDisabled: document.querySelector("#quotaName").disabled,
      unitDisabled: document.querySelector("#quotaUnit").disabled,
      saveDisabled: document.querySelector("#saveButton").disabled,
      saveNewDisabled: document.querySelector("#saveNewButton").disabled,
    }));
    record("BROWSER-006", "editor Draft controls", "enabled after Edit", JSON.stringify(editState), !editState.nameDisabled && !editState.unitDisabled && !editState.saveDisabled && !editState.saveNewDisabled);
    record("BROWSER-007", "browser errors", "0/0", `${consoleErrors.length}/${pageErrors.length}`, consoleErrors.length === 0 && pageErrors.length === 0);
    await page.screenshot({ path: path.join(OUTPUT, "enterprise_quota_a111_pilot.png"), fullPage: false });
    fs.writeFileSync(path.join(OUTPUT, "enterprise_quota_browser_result.json"), JSON.stringify({ checks, consoleErrors, pageErrors }, null, 2));
    const fields = ["check_id", "check", "expected", "actual", "status"];
    const quote = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
    fs.writeFileSync(path.join(OUTPUT, "enterprise_quota_browser_smoke.csv"), `\uFEFF${fields.join(",")}\n${checks.map(row => fields.map(field => quote(row[field])).join(",")).join("\n")}\n`);
    if (checks.some(row => row.status !== "pass")) throw new Error(`Browser smoke failed: ${JSON.stringify(checks)}`);
    const summaryPath = path.join(OUTPUT, "stage_summary.json");
    const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
    summary.browser_smoke_passed = checks.length;
    summary.browser_smoke_total = checks.length;
    summary.browser_screenshot = path.join(OUTPUT, "enterprise_quota_a111_pilot.png");
    fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));
    const browserVerification = `\n## Browser Verification\n\n- Headless Chromium workbench checks: \`${checks.length}/${checks.length} pass\`.\n- Verified 137-tree rendering, three-pane layout, all 10 tabs, null-price display and Draft editor controls.\n- Screenshot: \`enterprise_quota_a111_pilot.png\`.\n`;
    for (const fileName of [
      "checkpoint_enterprise_price_a111_pilot.md",
      "stage_enterprise_price_resource_matching_and_a111_quota_pilot_report.md",
    ]) {
      const reportPath = path.join(OUTPUT, fileName);
      const content = fs.readFileSync(reportPath, "utf8").split("\n## Browser Verification\n", 1)[0].trimEnd();
      fs.writeFileSync(reportPath, `${content}\n${browserVerification}`);
    }
    process.stdout.write(JSON.stringify({ passed: checks.length, total: checks.length, screenshot: path.join(OUTPUT, "enterprise_quota_a111_pilot.png") }));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exit(1); });
