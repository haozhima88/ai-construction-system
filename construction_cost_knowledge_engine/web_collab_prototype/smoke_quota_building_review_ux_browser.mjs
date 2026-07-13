import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const skipScreenshots = process.env.SKIP_SCREENSHOTS === "1";

const projectRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1")), "..", "..");
const engineRoot = path.join(projectRoot, "construction_cost_knowledge_engine");
const output = path.join(engineRoot, "data", "private", "reference_extraction", "runs", "WEB_QUOTA_BUILDING_REVIEW_UX_ENHANCEMENT_1");
fs.mkdirSync(output, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  args: ["--disable-gpu", "--disable-features=CalculateNativeWinOcclusion"],
});
const page = await browser.newPage({ viewport: { width: 1728, height: 900 }, deviceScaleFactor: 1 });
const consoleErrors = [];
const pageErrors = [];
page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("pageerror", error => pageErrors.push(error.message));

async function waitForWorkbench() {
  await page.waitForFunction(() => document.querySelector("#treeMeta")?.textContent?.startsWith("472 / 472"));
}

async function selectBill(code) {
  await page.evaluate(async value => window.selectBill(value), code);
  await page.waitForFunction(value => document.querySelector("#mainTitle")?.textContent?.includes(value), code);
}

async function selectQuota(code) {
  const candidate = page.locator("#mainRows tr[data-index]").filter({ hasText: code });
  if (await candidate.count() !== 1) throw new Error(`Expected one quota row for ${code}`);
  await candidate.click();
  await page.waitForFunction(value => document.querySelector("#detailMeta")?.textContent?.includes("PDF") && [...document.querySelectorAll("#mainRows tr.selected")].some(row => row.textContent.includes(value)), code);
}

async function clickTab(name) {
  const button = page.getByRole("button", { name, exact: true });
  if (await button.count() !== 1) throw new Error(`Expected one tab named ${name}`);
  await button.click();
}

async function screenshot(name) {
  if (skipScreenshots) return;
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.waitForTimeout(180);
  await page.screenshot({ path: path.join(output, name), fullPage: false });
}

async function geometry() {
  return page.evaluate(() => {
    const box = selector => {
      const element = document.querySelector(selector);
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom,
        overflowX: style.overflowX, overflowY: style.overflowY, scrollWidth: element.scrollWidth,
        scrollHeight: element.scrollHeight, clientWidth: element.clientWidth, clientHeight: element.clientHeight,
      };
    };
    return {
      workspace: box("#quotaWorkspace"), tree: box(".tree-panel"), center: box(".center-shell"), detail: box(".detail-panel"),
      tableScroll: box(".table-scroll"), tabContent: box("#tabContent"), main: box(".main-panel"), bottom: box(".bottom-panel"),
      leftSplitter: box("#leftSplitter"), rightSplitter: box("#rightSplitter"), horizontalSplitter: box("#horizontalSplitter"),
      gridColumns: getComputedStyle(document.querySelector("#quotaWorkspace")).gridTemplateColumns,
      gridRows: getComputedStyle(document.querySelector(".center-shell")).gridTemplateRows,
    };
  });
}

async function drag(selector, deltaX, deltaY) {
  const handle = page.locator(selector);
  const box = await handle.boundingBox();
  if (!box) throw new Error(`Missing splitter ${selector}`);
  const start = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + deltaX, start.y + deltaY, { steps: 8 });
  await page.mouse.up();
}

const results = { consoleErrors, pageErrors, targets: {}, structured: {}, layout: {} };
try {
  await page.goto("http://127.0.0.1:8006/quota-building", { waitUntil: "domcontentloaded" });
  await waitForWorkbench();
  await page.evaluate(() => localStorage.removeItem("quotaBuildingReviewLayoutV1"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForWorkbench();

  await page.evaluate(() => document.querySelectorAll(".tree-group>button").forEach(button => {
    const label = button.querySelector(".tree-label");
    if (label) label.textContent = button.title;
  }));
  await screenshot("before_tree_redundant_labels.png");
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForWorkbench();

  const treeLabels = await page.locator(".tree-group>button .tree-label").allTextContents();
  const treeTitles = await page.locator(".tree-group>button").evaluateAll(buttons => buttons.map(button => ({ code: button.dataset.appendixCode, title: button.title })));
  results.tree = {
    count: treeLabels.length,
    labels: treeLabels,
    titles: treeTitles,
    redundantPrefixCount: treeLabels.filter(label => /^附录[A-Z]/.test(label.trim())).length,
    hasEarthwork: treeLabels.includes("土石方工程"),
    hasFoundationSupport: treeLabels.includes("地基处理与边坡支护工程"),
  };
  await selectBill("010103001");
  await selectQuota("A1-1-1");
  await screenshot("after_tree_simplified_labels.png");

  const initialGeometry = await geometry();
  await drag("#leftSplitter", 42, 0);
  await drag("#rightSplitter", -36, 0);
  await drag("#horizontalSplitter", 0, -54);
  const draggedGeometry = await geometry();
  const storedLayout = await page.evaluate(() => JSON.parse(localStorage.getItem("quotaBuildingReviewLayoutV1") || "null"));
  await screenshot("after_resizable_layout.png");
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForWorkbench();
  const reloadedGeometry = await geometry();
  results.layout = { initialGeometry, draggedGeometry, storedLayout, reloadedGeometry };

  await selectBill("010103001");
  await selectQuota("A1-1-1");
  await clickTab("工作内容");
  await page.waitForSelector(".structured-table");
  results.structured.work = {
    rowCount: await page.locator(".structured-table tbody tr").count(),
    headers: await page.locator(".structured-table th").allTextContents(),
    firstRows: await page.locator(".structured-table tbody tr").evaluateAll(rows => rows.slice(0, 4).map(row => row.textContent.trim())),
    mode: "structured",
  };
  await screenshot("after_work_content_structured.png");
  const rawButton = page.getByRole("button", { name: "原文视图", exact: true });
  if (await rawButton.count() !== 1) throw new Error("Raw view toggle missing");
  await rawButton.click();
  results.structured.work.rawRecordCount = await page.locator(".raw-record").count();
  results.structured.work.rawTextPresent = (await page.locator(".raw-record-text").count()) > 0;
  await screenshot("after_raw_vs_structured_toggle.png");

  await clickTab("工程量规则");
  await page.waitForSelector(".structured-table");
  results.structured.rules = {
    rowCount: await page.locator(".structured-table tbody tr").count(),
    headers: await page.locator(".structured-table th").allTextContents(),
    levels: await page.locator(".structured-table tbody tr td:first-child").evaluateAll(cells => [...new Set(cells.slice(0, 80).map(cell => cell.textContent.trim()))]),
    pdfLinks: await page.locator(".structured-table .pdf-page-link").count(),
  };
  await screenshot("after_quantity_rule_structured.png");
  await page.getByRole("button", { name: "原文视图", exact: true }).click();
  results.structured.rules.rawRecordCount = await page.locator(".raw-record").count();

  await clickTab("换算规则");
  await page.waitForSelector(".structured-table");
  results.structured.conversions = {
    rowCount: await page.locator(".structured-table tbody tr").count(),
    headers: await page.locator(".structured-table th").allTextContents(),
    pdfLinks: await page.locator(".structured-table .pdf-page-link").count(),
  };
  await screenshot("after_conversion_rule_structured.png");
  await page.getByRole("button", { name: "原文视图", exact: true }).click();
  results.structured.conversions.rawRecordCount = await page.locator(".raw-record").count();

  await clickTab("注释");
  await page.waitForSelector(".structured-table");
  results.structured.notes = {
    rowCount: await page.locator(".structured-table tbody tr").count(),
    headers: await page.locator(".structured-table th").allTextContents(),
    pdfLinks: await page.locator(".structured-table .pdf-page-link").count(),
  };
  await screenshot("after_note_structured.png");
  await page.getByRole("button", { name: "原文视图", exact: true }).click();
  results.structured.notes.rawRecordCount = await page.locator(".raw-record").count();

  const tabScroll = await page.locator("#tabContent").evaluate(element => { element.scrollTop = Math.min(120, element.scrollHeight - element.clientHeight); return { top: element.scrollTop, independent: element.scrollHeight > element.clientHeight }; });
  const detailBefore = await page.locator(".detail-panel").boundingBox();
  const horizontalScroll = await page.locator(".table-scroll").evaluate(element => { element.scrollLeft = element.scrollWidth - element.clientWidth; return { left: element.scrollLeft, max: element.scrollWidth - element.clientWidth, overflowX: getComputedStyle(element).overflowX }; });
  const detailAfter = await page.locator(".detail-panel").boundingBox();
  results.layout.independentScroll = { tabScroll, horizontalScroll, detailStable: Math.abs(detailBefore.x - detailAfter.x) < 0.5 };

  for (const [billCode, expectedQuota, key] of [
    ["010202005", "A1-2-44", "precastPile"],
    ["010101001", "A1-1-35", "singleExcavation"],
    ["011101001", "A1-12-95", "A02"],
    ["011601001", "A1-21-127", "A03"],
  ]) {
    await selectBill(billCode);
    const row = page.locator("#mainRows tr[data-index]").filter({ hasText: expectedQuota });
    results.targets[key] = { billCode, expectedQuota, rowCount: await row.count(), highRiskVisible: (await row.count()) === 1 ? (await row.textContent()).includes("high") : false };
  }

  const reset = page.getByRole("button", { name: "默认布局", exact: true });
  if (await reset.count() !== 1) throw new Error("Reset layout button missing");
  await reset.click();
  results.layout.afterReset = await geometry();
  results.layout.storageAfterReset = await page.evaluate(() => localStorage.getItem("quotaBuildingReviewLayoutV1"));
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(output, "browser_review_ux_results.json"), JSON.stringify(results, null, 2), "utf8");
console.log(JSON.stringify({
  tree: results.tree,
  structured: results.structured,
  layout: {
    storedLayout: results.layout.storedLayout,
    independentScroll: results.layout.independentScroll,
    storageAfterReset: results.layout.storageAfterReset,
  },
  targets: results.targets,
  consoleErrors,
  pageErrors,
}, null, 2));
