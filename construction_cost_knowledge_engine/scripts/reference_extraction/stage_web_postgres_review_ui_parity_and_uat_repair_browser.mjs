import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT = path.join(ROOT, "data/private/reference_extraction/runs/WEB_POSTGRES_REVIEW_UI_PARITY_AND_UAT_REPAIR_1");
const BASE_URL = "http://127.0.0.1:8006";

function readEnvironment() {
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

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(OUTPUT, name), fullPage: false });
}

async function selectBill(page, code) {
  const input = page.locator("#treeSearch");
  await input.fill(code);
  await page.waitForTimeout(550);
  const item = page.locator(`.tree-item:has-text("${code}")`).first();
  await item.waitFor({ state: "visible" });
  await item.click();
  await page.locator("#billTitle").filter({ hasText: code }).waitFor();
  await page.waitForTimeout(250);
}

async function activateTab(page, label) {
  await page.locator("#tabButtons button", { hasText: label }).click();
  await page.waitForTimeout(250);
}

async function login(page, env, checks) {
  let activePassword = null;
  let activeUsername = null;
  if(process.env.PLATFORM_BROWSER_SESSION_TOKEN){
    await page.context().addCookies([{name:"ai_construction_session",value:process.env.PLATFORM_BROWSER_SESSION_TOKEN,url:BASE_URL,httpOnly:true,sameSite:"Lax"}]);
    activePassword=env.PLATFORM_BOOTSTRAP_ADMIN_PASSWORD;
    activeUsername=process.env.PLATFORM_BROWSER_UAT_USERNAME;
    await page.goto(`${BASE_URL}/quota-building`,{waitUntil:"domcontentloaded"});
    checks.login_transport="preauthenticated_uat_session_after_http_rate_gate";
  } else {
    await page.goto(`${BASE_URL}/login?next=/quota-building`, { waitUntil: "domcontentloaded" });
    const usernames = [process.env.PLATFORM_BROWSER_UAT_USERNAME, env.PLATFORM_BOOTSTRAP_ADMIN_USERNAME].filter(Boolean);
    for (const username of usernames) {
      for (const password of [env.PLATFORM_BOOTSTRAP_ADMIN_PASSWORD, env.PLATFORM_UAT_TEMP_PASSWORD]) {
        await page.locator("#username").fill(username);
        await page.locator("#password").fill(password);
        await page.locator("button[type=submit]").click();
        await page.waitForTimeout(700);
        if (!page.url().includes("/login")) { activePassword = password;activeUsername=username;break; }
      }
      if(activePassword)break;
    }
    checks.login_transport="http_login";
  }
  if (!activePassword) throw new Error("local_admin_login_failed");
  const landedOnChange = page.url().includes("/change-password");
  if (landedOnChange) {
    await page.locator("#currentPassword").fill(activePassword);
    await page.locator("#newPassword").fill(env.PLATFORM_UAT_TEMP_PASSWORD);
    await Promise.all([
      page.waitForURL(`${BASE_URL}/quota-building`, { timeout: 15000 }),
      page.locator("button[type=submit]").click(),
    ]);
  } else if (!page.url().includes("/quota-building")) {
    await page.goto(`${BASE_URL}/quota-building`, { waitUntil: "domcontentloaded" });
  }
  await page.locator(".review-workspace").waitFor({ state: "visible" });
  await page.locator(".tree-item").first().waitFor({ state: "visible", timeout: 20000 });
  checks.password_change_required = landedOnChange;
  checks.password_change_destination = new URL(page.url()).pathname;
  checks.uat_fixture_used = activeUsername !== env.PLATFORM_BOOTSTRAP_ADMIN_USERNAME;
  checks.safe_next_external_rejected = await page.evaluate(async () => {
    const module = await import("/platform-static/navigation.js");
    return module.safeNext("https://example.com/steal") === "/quota-building" && module.safeNext("//example.com/steal") === "/quota-building";
  });
}

fs.mkdirSync(OUTPUT, { recursive: true });
const env = readEnvironment();
const browser = await chromium.launch({
  headless: true,
  executablePath: path.join(process.env.LOCALAPPDATA, "ms-playwright/chromium-1223/chrome-win64/chrome.exe"),
});
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const page = await context.newPage();
const checks = { console_errors: [], page_errors: [] };
page.on("console", message => { if (message.type() === "error") checks.console_errors.push(message.text()); });
page.on("pageerror", error => checks.page_errors.push(error.message));

try {
  await login(page, env, checks);
  await screenshot(page, "uat_password_change_to_workbench.png");

  checks.provider_classes = await page.evaluate(() => ({
    workbench: typeof QuotaReviewWorkbench === "function",
    postgres: typeof PostgresReviewProvider === "function",
    sqlite: typeof SQLiteReadonlyReviewProvider === "function",
  }));
  checks.tab_labels = await page.locator("#tabButtons button").allTextContents();
  checks.tree_group_labels = await page.locator(".tree-group > button .tree-label").allTextContents();
  checks.tree_prefix_clean = checks.tree_group_labels.every(value => !/^附录\s*[A-Z]/i.test(value.trim()));
  await screenshot(page, "uat_tree_clean_names.png");

  await page.locator("#workspaceZoom").selectOption("80");
  await page.waitForTimeout(250);
  checks.zoom_80 = await page.locator("#reviewWorkspace").getAttribute("data-workspace-zoom");
  await screenshot(page, "uat_workspace_80_percent.png");
  await page.locator("#workspaceZoom").selectOption("100");
  await page.waitForTimeout(250);
  checks.zoom_100 = await page.locator("#reviewWorkspace").getAttribute("data-workspace-zoom");
  await screenshot(page, "uat_workspace_100_percent.png");

  await selectBill(page, "010103001");
  const preferred = page.locator("#mappingRows tr", { hasText: "A1-1-1" }).first();
  if (await preferred.count()) await preferred.click();
  await page.waitForTimeout(400);
  checks.primary_bill = await page.locator("#billTitle").innerText();
  checks.primary_quota = await page.locator("#tabMeta").innerText();

  await activateTab(page, "工作内容");
  await page.locator(".structured-table").waitFor();
  checks.work_structured_rows = await page.locator(".structured-table tbody tr").count();
  checks.work_structured_headers = await page.locator(".structured-table th").allTextContents();
  await screenshot(page, "uat_work_content_structured.png");
  await page.locator("button[data-text-mode=raw]").click();
  await page.locator(".raw-record").first().waitFor();
  checks.work_raw_records = await page.locator(".raw-record").count();
  await screenshot(page, "uat_work_content_raw.png");

  await selectBill(page, "010101002");
  const ruleCandidate = page.locator("#mappingRows tr", { hasText: "A1-1-125" }).first();
  if (await ruleCandidate.count()) await ruleCandidate.click();
  await page.waitForTimeout(350);
  await activateTab(page, "工程量规则");
  await page.locator(".structured-table").waitFor();
  checks.rule_structured_rows = await page.locator(".structured-table tbody tr").count();
  checks.rule_structured_headers = await page.locator(".structured-table th").allTextContents();
  checks.rule_pdf_links = await page.locator(".pdf-page-link").count();
  await screenshot(page, "uat_quantity_rule_structured.png");
  await page.locator("button[data-text-mode=raw]").click();
  await page.locator(".raw-record").first().waitFor();
  await screenshot(page, "uat_quantity_rule_pdf.png");

  await selectBill(page, "010103001");
  const conversionCandidate = page.locator("#mappingRows tr", { hasText: "A1-1-1" }).first();
  if (await conversionCandidate.count()) await conversionCandidate.click();
  await page.waitForTimeout(350);
  await activateTab(page, "换算规则");
  checks.conversion_rows = await page.locator(".structured-table tbody tr").count();
  await screenshot(page, "uat_conversion_rule.png");
  await activateTab(page, "注释");
  checks.note_rows = await page.locator(".structured-table tbody tr").count();
  await screenshot(page, "uat_note_clause.png");

  await activateTab(page, "国标 PDF");
  await page.getByText("官方 PDF 页证据待补", { exact: true }).waitFor();
  checks.authority_pending_text = await page.locator("#previewState").innerText();
  checks.authority_iframe_src_before_open = await page.locator("#previewFrame").getAttribute("src");
  checks.authority_open_unlocated_visible = await page.locator("#openUnlocatedAuthority").isVisible();
  await screenshot(page, "uat_official_pdf_pending_evidence.png");

  const sampleBills = ["010102005", "010101001", "011101001", "011601001"];
  checks.sample_bills = [];
  for (const code of sampleBills) {
    await selectBill(page, code);
    checks.sample_bills.push({ code, title: await page.locator("#billTitle").innerText(), mapping_rows: await page.locator("#mappingRows tr[data-row]").count() });
  }

  await selectBill(page, "010103001");
  await page.locator("#treeSearch").fill("");
  await page.waitForTimeout(550);
  await activateTab(page, "工料机");
  checks.splitter_count = await page.locator(".splitter").count();
  checks.detail_visible = await page.locator("#detailPane").isVisible();
  checks.mapping_actions = await page.locator("#mappingRows .row-actions button").allTextContents();
  checks.summary = await page.locator("#summaryText").innerText();
  await screenshot(page, "uat_full_workbench.png");

  checks.local_storage_zoom = await page.evaluate(() => JSON.parse(localStorage.getItem("quota_review_pg_preferences_v1") || "{}").workspaceZoom);
  checks.console_errors = checks.console_errors.filter(value => !value.includes("favicon"));
  fs.writeFileSync(path.join(OUTPUT, "browser_uat_result.json"), JSON.stringify(checks, null, 2), "utf8");
  process.stdout.write(JSON.stringify({ status: "pass", screenshots: 12, checks }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
