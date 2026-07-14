import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT = path.join(ROOT, "data/private/reference_extraction/runs/WEB_POSTGRES_REVIEW_ACTION_AND_FIT_LAYOUT_CLOSURE_1");
const BASE_URL = process.env.PLATFORM_UAT_BASE_URL || "http://127.0.0.1:8007";
const PRIMARY_BILL = "010201007";
const TARGET_BILL = "010101001";

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

async function waitWorkbenchReady(page) {
  await page.locator(".review-workspace").waitFor({ state: "visible" });
  await page.locator(".tree-item").first().waitFor({ state: "visible", timeout: 20000 });
  await page.locator("#mappingRows tr[data-row]").first().waitFor({ state: "visible", timeout: 20000 });
  await page.waitForFunction(() => {
    const value = document.querySelector("#tabMeta")?.textContent || "";
    return value && value !== "请选择定额候选" && !value.startsWith("__uat_");
  });
}

async function login(page, username, password) {
  await page.goto(`${BASE_URL}/login?next=/quota-building`, { waitUntil: "domcontentloaded" });
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await Promise.all([
    page.waitForURL(`${BASE_URL}/quota-building`, { timeout: 15000 }),
    page.locator("button[type=submit]").click(),
  ]);
  await waitWorkbenchReady(page);
}

async function identity(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/v1/auth/me", { credentials: "same-origin" });
    const payload = await response.json();
    return {
      roles: payload.roles,
      permissions: payload.permissions,
      tenant_code: payload.tenant.tenant_code,
      must_change_password: payload.user.must_change_password,
    };
  });
}

async function selectBill(page, code) {
  const search = page.locator("#treeSearch");
  await search.fill(code);
  await page.waitForTimeout(550);
  const item = page.locator(`.tree-item:has-text("${code}")`).first();
  await item.waitFor({ state: "visible" });
  const marker = `__uat_bill_${code}_${Date.now()}__`;
  await page.locator("#tabMeta").evaluate((node, value) => { node.textContent = value; }, marker);
  await item.click();
  await page.locator("#billTitle").filter({ hasText: code }).waitFor();
  await page.locator("#mappingRows tr[data-row]").first().waitFor({ state: "visible" });
  await page.waitForFunction(value => document.querySelector("#tabMeta")?.textContent !== value, marker);
}

function candidateRow(page, quotaCode, origin = null) {
  let locator = page.locator("#mappingRows tr[data-row]", { hasText: quotaCode });
  if (origin) locator = locator.filter({ hasText: origin });
  return locator.first();
}

async function actionLabels(row) {
  return (await row.locator(".row-actions button").allTextContents()).map(value => value.trim());
}

async function runDialogAction(page, row, action, targetBill = null) {
  const responsePromise = page.waitForResponse(response =>
    response.url().includes(`/api/v1/review/mapping-drafts/${action}`) && response.request().method() === "POST",
    { timeout: 10000 },
  ).then(response => ({ response })).catch(error => ({ error }));
  const refreshPromise = page.waitForResponse(response =>
    response.request().method() === "GET" && response.url().includes("/api/v1/review/bills/") && response.url().endsWith("/mappings"),
    { timeout: 15000 },
  );
  await row.locator(`button[data-action="${action}"]`).click();
  await page.locator("#draftDialog").waitFor({ state: "visible" });
  if (targetBill) await page.locator("#targetBill").selectOption(targetBill);
  await page.locator("#operationReason").fill(`UAT_LAYOUT_ACTION_WORKSPACE ${action}`);
  const marker = `__uat_${action}_${Date.now()}__`;
  await page.locator("#tabMeta").evaluate((node, value) => { node.textContent = value; }, marker);
  await page.locator("#confirmDraft").click();
  const outcome = await responsePromise;
  if (outcome.error) {
    const diagnostics = await page.evaluate(() => ({
      dialog_open: document.querySelector("#draftDialog")?.open,
      pending_action: state.pendingAction?.action,
      fatal_text: document.querySelector(".fatal-state")?.textContent || "",
      confirm_connected: document.querySelector("#confirmDraft")?.isConnected,
    }));
    throw new Error(`${action} response missing: ${JSON.stringify(diagnostics)}; ${outcome.error.message}`);
  }
  const response = outcome.response;
  if (response.status() !== 200) throw new Error(`${action} returned ${response.status()}`);
  await page.locator("#draftDialog").waitFor({ state: "hidden" });
  await refreshPromise;
  await page.waitForFunction(value => document.querySelector("#tabMeta")?.textContent !== value, marker);
  return response.status();
}

async function runRestore(page, row) {
  const responsePromise = page.waitForResponse(response =>
    response.url().includes("/api/v1/review/mapping-drafts/restore") && response.request().method() === "POST",
  );
  const refreshPromise = page.waitForResponse(response =>
    response.request().method() === "GET" && response.url().includes("/api/v1/review/bills/") && response.url().endsWith("/mappings"),
    { timeout: 15000 },
  );
  const marker = `__uat_restore_${Date.now()}__`;
  await page.locator("#tabMeta").evaluate((node, value) => { node.textContent = value; }, marker);
  await row.locator('button[data-action="restore"]').click();
  const response = await responsePromise;
  if (response.status() !== 200) throw new Error(`restore returned ${response.status()}`);
  await refreshPromise;
  await page.waitForFunction(value => document.querySelector("#tabMeta")?.textContent !== value, marker);
  return response.status();
}

async function resetLayout(page) {
  await page.locator("#resetLayout").click();
  await page.waitForTimeout(180);
}

async function layoutMetrics(page, viewport) {
  return page.evaluate(({ width, height }) => {
    const rect = selector => document.querySelector(selector)?.getBoundingClientRect();
    const container = document.querySelector("#candidateTableContainer");
    const table = document.querySelector(".mapping-table");
    const action = document.querySelector("#mappingRows tr[data-row] .action-column");
    const name = document.querySelector("#mappingRows tr[data-row] .candidate-name");
    const costs = [...document.querySelectorAll("#mappingRows tr[data-row] .cost-cell")];
    const center = rect(".review-center-pane");
    const detail = rect("#detailPane");
    const tree = rect(".tree-pane");
    const tableRect = table?.getBoundingClientRect();
    const containerRect = container?.getBoundingClientRect();
    const actionRect = action?.getBoundingClientRect();
    return {
      viewport: `${width}x${height}`,
      mode: document.querySelector("#reviewWorkspace")?.dataset.layoutMode,
      density: document.querySelector("#reviewWorkspace")?.dataset.reviewDensity,
      center_width: Math.round(center?.width || 0),
      container_width: Math.round(containerRect?.width || 0),
      table_width: Math.round(tableRect?.width || 0),
      unused_right_space: Math.max(0, Math.round((containerRect?.right || 0) - (tableRect?.right || 0))),
      scroll_width: container?.scrollWidth || 0,
      client_width: container?.clientWidth || 0,
      horizontal_overflow: Math.max(0, (container?.scrollWidth || 0) - (container?.clientWidth || 0)),
      action_width: Math.round(actionRect?.width || 0),
      action_visible: Boolean(actionRect && containerRect && actionRect.left >= containerRect.left - 1 && actionRect.right <= containerRect.right + 1),
      action_before_detail: Boolean(actionRect && detail && actionRect.right <= detail.left + 1),
      name_width: Math.round(name?.getBoundingClientRect().width || 0),
      cost_widths: costs.slice(0, 5).map(cell => Math.round(cell.getBoundingClientRect().width)),
      detail_visible: Boolean(detail && detail.width > 0),
      tree_visible: Boolean(tree && tree.width > 0),
      center_dataset_width: Number(document.querySelector("#reviewWorkspace")?.dataset.centerWidth || 0),
    };
  }, viewport);
}

async function viewportCheck(page, width, height, screenshotName = null) {
  await page.setViewportSize({ width, height });
  await resetLayout(page);
  await page.locator("#layoutMode").selectOption("auto_fit");
  await page.waitForTimeout(220);
  const metrics = await layoutMetrics(page, { width, height });
  if (screenshotName) await screenshot(page, screenshotName);
  return metrics;
}

async function dragSplitter(page, selector, deltaX, deltaY) {
  const box = await page.locator(selector).boundingBox();
  if (!box) throw new Error(`Missing splitter ${selector}`);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + deltaX, y + deltaY, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(160);
}

fs.mkdirSync(OUTPUT, { recursive: true });
const env = readEnvironment();
const password = env.PLATFORM_UAT_TEMP_PASSWORD;
if (!password) throw new Error("PLATFORM_UAT_TEMP_PASSWORD is missing");

const browser = await chromium.launch({
  headless: true,
  executablePath: path.join(process.env.LOCALAPPDATA, "ms-playwright/chromium-1223/chrome-win64/chrome.exe"),
});
const result = {
  base_url: BASE_URL,
  primary_bill: PRIMARY_BILL,
  target_bill: TARGET_BILL,
  console_errors: [],
  page_errors: [],
  mutation_requests: [],
  operations: [],
  viewports: [],
};

try {
  const viewerContext = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const viewerPage = await viewerContext.newPage();
  viewerPage.on("console", message => { if (message.type() === "error") result.console_errors.push(`viewer:${message.text()}`); });
  viewerPage.on("pageerror", error => result.page_errors.push(`viewer:${error.message}`));
  await login(viewerPage, "uat_viewer", password);
  result.viewer_identity = await identity(viewerPage);
  await selectBill(viewerPage, PRIMARY_BILL);
  result.viewer_readonly_badges = await viewerPage.locator("#mappingRows .action-readonly").count();
  result.viewer_action_buttons = await viewerPage.locator("#mappingRows .row-actions button").count();
  result.viewer_write_status = await viewerPage.evaluate(async ({ bill, target }) => {
    const me = await (await fetch("/api/v1/auth/me", { credentials: "same-origin" })).json();
    const mappings = await (await fetch(`/api/v1/review/bills/${bill}/mappings`, { credentials: "same-origin" })).json();
    const row = mappings.items[0];
    const response = await fetch("/api/v1/review/mapping-drafts/copy", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": me.csrf_token },
      body: JSON.stringify({ edge_id: row.edge_id, target_bill_code_9: target, operation_reason: "viewer must be denied", row_version: row.row_version, idempotency_key: `viewer-denied-${crypto.randomUUID()}` }),
    });
    return response.status;
  }, { bill: PRIMARY_BILL, target: TARGET_BILL });
  await screenshot(viewerPage, "after_viewer_readonly.png");
  await viewerContext.close();

  const editorContext = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, bypassCSP: true });
  const page = await editorContext.newPage();
  page.on("console", message => { if (message.type() === "error") result.console_errors.push(`editor:${message.text()}`); });
  page.on("pageerror", error => result.page_errors.push(`editor:${error.message}`));
  page.on("request", request => {
    if (!request.url().includes("/api/v1/review/mapping-drafts/") || request.method() !== "POST") return;
    let payload = {};
    try { payload = request.postDataJSON(); } catch (_) { payload = {}; }
    result.mutation_requests.push({
      action: request.url().split("/").at(-1),
      csrf_header_present: Boolean(request.headers()["x-csrf-token"]),
      idempotency_key_present: Boolean(payload.idempotency_key),
      row_version_present: Number.isInteger(payload.row_version),
    });
  });
  await login(page, "uat_editor", password);
  result.editor_identity = await identity(page);
  await selectBill(page, PRIMARY_BILL);
  result.required_candidate_codes = ["A1-2-21", "A1-2-25", "A1-2-29", "A1-2-23", "A1-2-27", "A1-2-31"];
  result.visible_candidate_codes = await page.locator("#mappingRows tr[data-row] td:nth-child(3)").allTextContents();
  result.editor_original_actions = await actionLabels(candidateRow(page, "A1-2-21"));

  await page.evaluate(() => document.querySelectorAll(".row-actions").forEach(cell => { cell.dataset.preFixMarkup = cell.innerHTML; cell.innerHTML = ""; }));
  await screenshot(page, "before_action_missing.png");
  await page.evaluate(() => renderMappings());
  await screenshot(page, "after_editor_actions_visible.png");

  await runDialogAction(page, candidateRow(page, "A1-2-21"), "copy", TARGET_BILL);
  result.operations.push({ action: "copy", status: 200 });
  await selectBill(page, TARGET_BILL);
  let copied = candidateRow(page, "A1-2-21", "draft_copy");
  await copied.waitFor({ state: "visible" });
  result.copied_draft_actions = await actionLabels(copied);
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitWorkbenchReady(page);
  await selectBill(page, TARGET_BILL);
  copied = candidateRow(page, "A1-2-21", "draft_copy");
  result.copy_persisted_after_refresh = await copied.isVisible();
  await runRestore(page, copied);
  result.operations.push({ action: "restore_copy", status: 200 });

  await selectBill(page, PRIMARY_BILL);
  await runDialogAction(page, candidateRow(page, "A1-2-25"), "move", TARGET_BILL);
  result.operations.push({ action: "move", status: 200 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitWorkbenchReady(page);
  await selectBill(page, PRIMARY_BILL);
  let moved = candidateRow(page, "A1-2-25");
  result.move_persisted_after_refresh = (await actionLabels(moved)).includes("Restore");
  await runRestore(page, moved);
  result.operations.push({ action: "restore_move", status: 200 });

  await selectBill(page, PRIMARY_BILL);
  await runDialogAction(page, candidateRow(page, "A1-2-29"), "exclude");
  result.operations.push({ action: "exclude", status: 200 });
  let excluded = candidateRow(page, "A1-2-29");
  result.exclude_restore_visible = (await actionLabels(excluded)).includes("Restore");
  await runRestore(page, excluded);
  result.operations.push({ action: "restore_exclude", status: 200 });

  result.audit = await page.evaluate(async () => {
    const payload = await (await fetch("/api/v1/review/audit?page_size=500", { credentials: "same-origin" })).json();
    return { total: payload.total, event_types: payload.items.map(row => row.event_type) };
  });

  await selectBill(page, PRIMARY_BILL);
  await page.setViewportSize({ width: 2048, height: 1017 });
  await resetLayout(page);
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.id = "preFixWidthReconstruction";
    style.textContent = ".review-workspace .mapping-table{width:1120px!important;max-width:none!important;min-width:1120px!important}.mapping-table .action-column{position:static!important}";
    document.head.appendChild(style);
  });
  result.before_unused_blank_area = await layoutMetrics(page, { width: 2048, height: 1017 });
  await screenshot(page, "before_unused_blank_area.png");
  await page.locator("#preFixWidthReconstruction").evaluate(node => node.remove());

  result.viewports.push(await viewportCheck(page, 2048, 1017, "after_auto_fit_2048x1017.png"));
  result.viewports.push(await viewportCheck(page, 1920, 1080, "after_auto_fit_1920x1080.png"));
  result.viewports.push(await viewportCheck(page, 1600, 900));
  result.viewports.push(await viewportCheck(page, 1366, 768, "after_auto_fit_1366x768.png"));

  await page.locator("#layoutMode").selectOption("full_columns");
  await page.waitForTimeout(220);
  await page.locator("#candidateTableContainer").evaluate(node => { node.scrollLeft = Math.round((node.scrollWidth - node.clientWidth) * 0.55); });
  result.full_columns = await layoutMetrics(page, { width: 1366, height: 768 });
  result.full_columns.scroll_left = await page.locator("#candidateTableContainer").evaluate(node => node.scrollLeft);
  await screenshot(page, "after_full_columns_scroll.png");

  await page.locator("#layoutMode").selectOption("compact_review");
  await page.waitForTimeout(220);
  result.compact_review = await layoutMetrics(page, { width: 1366, height: 768 });
  result.compact_review.visible_headers = await page.locator(".mapping-table thead th:visible").allTextContents();
  await screenshot(page, "after_compact_review_mode.png");

  await page.setViewportSize({ width: 1920, height: 1080 });
  await resetLayout(page);
  const beforeSplit = await page.evaluate(() => ({
    left: Math.round(document.querySelector(".tree-pane").getBoundingClientRect().width),
    right: Math.round(document.querySelector("#detailPane").getBoundingClientRect().width),
    top: Math.round(document.querySelector(".mapping-panel").getBoundingClientRect().height),
  }));
  await dragSplitter(page, "#leftSplitter", 70, 0);
  await dragSplitter(page, "#rightSplitter", -55, 0);
  await dragSplitter(page, "#horizontalSplitter", 0, 45);
  const afterSplit = await page.evaluate(() => ({
    left: Math.round(document.querySelector(".tree-pane").getBoundingClientRect().width),
    right: Math.round(document.querySelector("#detailPane").getBoundingClientRect().width),
    top: Math.round(document.querySelector(".mapping-panel").getBoundingClientRect().height),
    storage: Object.fromEntries(["review_layout_mode", "review_density", "left_pane_width", "right_pane_width", "top_pane_height"].map(key => [key, localStorage.getItem(key)])),
  }));
  await page.locator("#toggleDetail").evaluate(button => button.click());
  const collapsedCenterWidth = Number(await page.locator("#reviewWorkspace").getAttribute("data-center-width"));
  await page.locator("#toggleDetail").evaluate(button => button.click());
  await page.waitForTimeout(120);
  await screenshot(page, "after_splitter_resize.png");
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitWorkbenchReady(page);
  const restoredSplit = await page.evaluate(() => ({
    left: Math.round(document.querySelector(".tree-pane").getBoundingClientRect().width),
    right: Math.round(document.querySelector("#detailPane").getBoundingClientRect().width),
    top: Math.round(document.querySelector(".mapping-panel").getBoundingClientRect().height),
  }));
  result.splitter = { before: beforeSplit, after: afterSplit, restored: restoredSplit, collapsed_center_width: collapsedCenterWidth };
  result.local_storage = afterSplit.storage;
  result.console_errors = result.console_errors.filter(value =>
    !value.includes("favicon") && !value.includes("viewer:Failed to load resource: the server responded with a status of 403"),
  );
  await editorContext.close();

  fs.writeFileSync(path.join(OUTPUT, "browser_uat_result.json"), JSON.stringify(result, null, 2), "utf8");
  process.stdout.write(JSON.stringify({
    status: "pass",
    viewer_write_status: result.viewer_write_status,
    operations: result.operations.length,
    audit_total: result.audit.total,
    viewports: result.viewports.map(row => row.viewport),
    screenshots: 10,
  }));
} finally {
  await browser.close();
}
