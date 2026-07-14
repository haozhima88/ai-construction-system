const STORAGE_EXPANDED = "quota_a111_expanded_bills";
const STORAGE_PENDING_DRAFT = "quota_a111_pending_draft_payload";
const STORAGE_RULE_INDEX_HEIGHT = "quota_a111_rule_index_height";

const state = {
  treeRows: [],
  treeNodes: [],
  selectedBillCode: "",
  billRows: [],
  activeRow: null,
  activeQuotaCode: "",
  activeDetail: null,
  activeTab: "resources",
  expandedBills: new Set(JSON.parse(localStorage.getItem(STORAGE_EXPANDED) || "[]")),
  showExcluded: false,
  draftStats: {},
  dragPayload: null,
  pendingDraft: null,
  quantityRuleRows: [],
  activeRuleIndex: 0,
  quantityRuleView: "original",
  quantityRulePages: [],
  quantityRuleBlocks: [],
  quantityRulePageIndex: 0,
  quantityRuleZoom: "page-width",
  selectedRuleBlockId: "",
};

const el = {
  workspace: document.querySelector("#quotaWorkspace"),
  summaryPill: document.querySelector("#summaryPill"),
  draftStatsPill: document.querySelector("#draftStatsPill"),
  draftBreakdown: document.querySelector("#draftBreakdown"),
  draftMessage: document.querySelector("#draftMessage"),
  treeMeta: document.querySelector("#treeMeta"),
  treeSearchInput: document.querySelector("#treeSearchInput"),
  searchResults: document.querySelector("#searchResults"),
  treeRoot: document.querySelector("#treeRoot"),
  mainTitle: document.querySelector("#mainTitle"),
  mainMeta: document.querySelector("#mainMeta"),
  mainRows: document.querySelector("#mainRows"),
  collapseBtn: document.querySelector("#collapseBtn"),
  expandBtn: document.querySelector("#expandBtn"),
  showExcludedToggle: document.querySelector("#showExcludedToggle"),
  exportDraftBtn: document.querySelector("#exportDraftBtn"),
  exportAuditBtn: document.querySelector("#exportAuditBtn"),
  resetDraftBtn: document.querySelector("#resetDraftBtn"),
  tabButtons: document.querySelectorAll(".tab-button"),
  tabMeta: document.querySelector("#tabMeta"),
  tabContent: document.querySelector("#tabContent"),
  selectedDetails: document.querySelector("#selectedDetails"),
  pdfDetails: document.querySelector("#pdfDetails"),
  leftSplitter: document.querySelector("#leftSplitter"),
  rightSplitter: document.querySelector("#rightSplitter"),
  bottomSplitter: document.querySelector("#bottomSplitter"),
  draftModal: document.querySelector("#draftModal"),
  modalQuotaCode: document.querySelector("#modalQuotaCode"),
  modalQuotaName: document.querySelector("#modalQuotaName"),
  modalSourceBill: document.querySelector("#modalSourceBill"),
  modalTargetBill: document.querySelector("#modalTargetBill"),
  draftReasonInput: document.querySelector("#draftReasonInput"),
  confirmCopyBtn: document.querySelector("#confirmCopyBtn"),
  confirmMoveBtn: document.querySelector("#confirmMoveBtn"),
  confirmExcludeBtn: document.querySelector("#confirmExcludeBtn"),
  cancelDraftBtn: document.querySelector("#cancelDraftBtn"),
  cancelDraftBtn2: document.querySelector("#cancelDraftBtn2"),
};

const SELECTED_FIELDS = [
  ["行类型", "row_type"],
  ["关系类型", "relation_type"],
  ["GB/T 编码", "bill_code_9"],
  ["GB/T 名称", "bill_name"],
  ["定额编码", "quota_source_code"],
  ["定额名称", "quota_name_from_pdf"],
  ["单位", "quota_unit_normalized"],
  ["基价", "base_price"],
  ["映射角色", "mapping_role"],
  ["置信度", "mapping_confidence"],
  ["草稿状态", "draft_status"],
  ["草稿提示", "draft_warning"],
];

const PDF_FIELDS = [
  ["PDF 页码", "pdf_page_no"],
  ["书内页码", "book_page_no"],
  ["资源行数", "resource_row_count"],
  ["资源对账", "resource_reconciliation_status"],
  ["XLSX 对账", "match_status"],
  ["价差", "delta_total"],
  ["覆盖状态", "coverage_status"],
  ["高风险", "has_high_or_blocking_issue"],
  ["review", "review_status"],
];

function empty(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function html(value) {
  return empty(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function postApi(path, payload = {}) {
  return api(path, { method: "POST", body: JSON.stringify(payload) });
}

function showMessage(message, isError = false) {
  el.draftMessage.textContent = message;
  el.draftMessage.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function badgeClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("exclude") || text.includes("high") || text.includes("blocking") || text.includes("xlsx_only")) return "badge danger";
  if (text.includes("draft") || text.includes("pending") || text.includes("manual") || text.includes("review") || text.includes("gap")) return "badge warn";
  if (text.includes("complete") || text.includes("matched") || text.includes("low") || text.includes("original")) return "badge ok";
  return "badge";
}

function buildTree(rows) {
  const byId = new Map();
  const roots = [];
  rows.forEach((row) => byId.set(row.node_id, { ...row, children: [] }));
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) byId.get(node.parent_id).children.push(node);
    else roots.push(node);
  });
  return roots;
}

function filterTree(nodes, query) {
  if (!query) return nodes;
  const q = query.toLowerCase();
  const visit = (node) => {
    const children = node.children.map(visit).filter(Boolean);
    const text = [node.bill_code_9, node.bill_name, node.section_name, node.appendix_name].join(" ").toLowerCase();
    if (text.includes(q) || children.length) return { ...node, children, forceOpen: true };
    return null;
  };
  return nodes.map(visit).filter(Boolean);
}

function renderTree() {
  const query = el.treeSearchInput.value.trim();
  el.treeRoot.innerHTML = filterTree(state.treeNodes, query).map(renderTreeNode).join("");
  document.querySelectorAll(".tree-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const node = button.closest(".tree-node");
      if (node.dataset.type === "bill") {
        await selectBill(node.dataset.bill);
        return;
      }
      node.classList.toggle("expanded");
    });
  });
  document.querySelectorAll(".tree-node[data-type='bill']").forEach((node) => {
    node.addEventListener("dragover", (event) => handleDragOver(event, node));
    node.addEventListener("dragleave", () => node.classList.remove("drop-hover"));
    node.addEventListener("drop", (event) => handleDropToBill(event, node.dataset.bill, node.dataset.billName || ""));
  });
}

function renderTreeNode(node) {
  const expanded = node.forceOpen || node.node_type === "appendix" || node.node_type === "section" ? " expanded" : "";
  const active = node.bill_code_9 === state.selectedBillCode ? " active" : "";
  const counts = node.node_type === "bill"
    ? renderTreeDraftCounts(node)
    : `<span class="${badgeClass(node.risk_level)}">${html(node.candidate_quota_count || "")}</span>`;
  return `
    <div class="tree-node ${expanded}" data-type="${html(node.node_type)}" data-bill="${html(node.bill_code_9)}" data-bill-name="${html(node.bill_name)}">
      <button class="tree-button${active}" type="button">
        <span>${node.children.length ? "▾" : "•"}</span>
        <span class="tree-label" title="${html(node.bill_name || node.section_name || node.appendix_name)}">${html(node.bill_code_9 ? `${node.bill_code_9} ${node.bill_name}` : node.section_name || node.appendix_name)}</span>
        ${counts}
      </button>
      ${node.children.length ? `<div class="tree-children">${node.children.map(renderTreeNode).join("")}</div>` : ""}
    </div>
  `;
}

function renderTreeDraftCounts(node) {
  const original = Number(node.original_candidate_count || 0);
  const copyIn = Number(node.copy_in_count || 0);
  const moveIn = Number(node.move_in_count || 0);
  const moveOut = Number(node.move_out_count || 0);
  const excluded = Number(node.excluded_count || 0);
  const effective = Number(node.effective_candidate_count || 0);
  const reverted = Number(node.reverted_count || 0);
  const hasDraft = node.has_draft_change === true || String(node.has_draft_change).toLowerCase() === "true";
  const tooltip = [
    `原始候选 ${original}`,
    `Copy 新增 +${copyIn}`,
    `Move 迁入 +${moveIn}`,
    `Move 迁出 -${moveOut}`,
    `Exclude -${excluded}`,
    `当前有效 ${effective}`,
    `已恢复 edge ${reverted}`,
  ].join(" / ");
  if (!hasDraft) {
    return `<span class="tree-counts compact" title="${html(tooltip)}"><span class="tree-count-badge effective">${html(original)} / ${html(effective)}</span></span>`;
  }
  return `
    <span class="tree-counts" title="${html(tooltip)}">
      <span class="tree-count-badge original">原${html(original)}</span>
      ${copyIn ? `<span class="tree-count-badge copy">C+${html(copyIn)}</span>` : ""}
      ${moveIn ? `<span class="tree-count-badge move-in">M+${html(moveIn)}</span>` : ""}
      ${moveOut ? `<span class="tree-count-badge move-out">M-${html(moveOut)}</span>` : ""}
      ${excluded ? `<span class="tree-count-badge excluded">X-${html(excluded)}</span>` : ""}
      <span class="tree-count-badge effective">=${html(effective)}</span>
    </span>
  `;
}

function visibleRows() {
  return state.billRows.filter((row) => row.row_type === "gb_bill" || state.expandedBills.has(row.bill_code_9));
}

async function selectBill(billCode, quotaCode = "") {
  if (!billCode) return;
  state.selectedBillCode = billCode;
  const suffix = state.showExcluded ? "?include_excluded=true" : "";
  const data = await api(`/api/quota-a111/bill/${encodeURIComponent(billCode)}/rows${suffix}`);
  state.billRows = data.rows || [];
  updateDraftStats(data.draft_stats || {});
  state.expandedBills.add(billCode);
  persistExpanded();
  const bill = data.bill || {};
  el.mainTitle.textContent = `${billCode} ${bill.bill_name || ""}`;
  const billStats = data.bill_draft_stats || {};
  el.mainMeta.textContent = `有效 ${billStats.effective_candidate_count ?? data.candidate_count} / 原始关系 ${billStats.original_candidate_count ?? data.original_candidate_count} / 当前显示行 ${data.count} / pending draft`;
  renderTree();
  renderMainRows();
  const target = quotaCode
    ? state.billRows.find((row) => row.quota_source_code === quotaCode)
    : state.billRows.find((row) => row.row_type === "gd_quota_pdf_candidate" || row.row_type === "draft_copy" || row.row_type === "draft_move_target");
  await selectRow(target || state.billRows[0] || bill);
}

function persistExpanded() {
  localStorage.setItem(STORAGE_EXPANDED, JSON.stringify([...state.expandedBills]));
}

function updateDraftStats(stats = {}) {
  state.draftStats = stats;
  const total = Number(stats.total_count || 0);
  el.draftStatsPill.textContent = `草稿 ${total}`;
  el.draftBreakdown.textContent = `copy ${stats.copy_count || 0} / move ${stats.move_count || 0} / exclude ${stats.exclude_count || 0} / reverted ${stats.reverted_count || 0}`;
}

async function refreshTree() {
  const tree = await api("/api/quota-a111/tree");
  state.treeRows = tree.items || [];
  state.treeNodes = buildTree(state.treeRows);
  updateDraftStats(tree.draft_stats || {});
  el.summaryPill.textContent = `${tree.enabled_bill_count} bill / ${tree.main_quota_count} quota / ${tree.resource_row_count} resource`;
  el.treeMeta.textContent = `Appendix A enabled bill ${tree.enabled_bill_count}`;
  renderTree();
  return tree;
}

function isDraggableRow(row) {
  return ["gd_quota_pdf_candidate", "xlsx_only_supplemental", "draft_copy", "draft_move_target"].includes(row.row_type);
}

function renderMainRows() {
  const rows = visibleRows();
  if (!rows.length) {
    el.mainRows.innerHTML = `<tr><td colspan="14" class="empty-row">当前 bill 暂无定额候选</td></tr>`;
    return;
  }
  el.mainRows.innerHTML = rows.map(renderMainRow).join("");
  document.querySelectorAll("#mainRows tr[data-row-id]").forEach((tr) => {
    tr.addEventListener("click", async (event) => {
      if (event.target.closest("button,a,input,textarea,label")) return;
      const row = state.billRows.find((item) => item.row_id === tr.dataset.rowId);
      if (row) await selectRow(row);
    });
  });
  document.querySelectorAll("[data-action='select-row']").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const row = state.billRows.find((item) => item.row_id === button.dataset.rowId);
      if (row) await selectRow(row);
    });
  });
  document.querySelectorAll("[data-action='toggle-bill']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const bill = button.dataset.bill;
      if (state.expandedBills.has(bill)) state.expandedBills.delete(bill);
      else state.expandedBills.add(bill);
      persistExpanded();
      renderMainRows();
    });
  });
  document.querySelectorAll("[data-action='drag-handle']").forEach((button) => {
    button.addEventListener("dragstart", (event) => {
      event.stopPropagation();
      const row = state.billRows.find((item) => item.row_id === button.dataset.rowId);
      if (!row || !isDraggableRow(row)) return;
      state.dragPayload = draftPayloadFromRow(row);
      event.dataTransfer.effectAllowed = "copyMove";
      event.dataTransfer.setData("application/json", JSON.stringify(state.dragPayload));
    });
    button.addEventListener("click", (event) => event.stopPropagation());
  });
  document.querySelectorAll("[data-action='restore-draft']").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await restoreDraft(button.dataset.edgeId);
    });
  });
  document.querySelectorAll("#mainRows tr[data-drop-bill]").forEach((tr) => {
    tr.addEventListener("dragover", (event) => handleDragOver(event, tr));
    tr.addEventListener("dragleave", () => tr.classList.remove("drop-hover"));
    tr.addEventListener("drop", (event) => handleDropToBill(event, tr.dataset.dropBill, tr.dataset.billName || ""));
  });
}

function rowLabel(row) {
  if (row.row_type === "gb_bill") return "清单";
  if (row.row_type === "gd_quota_pdf_candidate") return "PDF";
  if (row.row_type === "xlsx_only_supplemental") return "XLSX";
  if (row.row_type === "draft_copy") return "draft_copy";
  if (row.row_type === "draft_move_target") return "draft_move";
  if (row.row_type === "draft_move_source_excluded") return "move_excluded";
  if (row.row_type === "draft_excluded") return "excluded";
  return "池";
}

function renderMainRow(row) {
  const active = row.row_id === state.activeRow?.row_id ? " row-active" : "";
  const draggable = isDraggableRow(row);
  const isBill = row.row_type === "gb_bill";
  const expander = isBill
    ? `<button class="link-button" data-action="toggle-bill" data-bill="${html(row.bill_code_9)}" type="button">${state.expandedBills.has(row.bill_code_9) ? "−" : "+"}</button>`
    : `${draggable ? `<button class="drag-handle" data-action="drag-handle" data-row-id="${html(row.row_id)}" draggable="true" title="拖动候选关系草稿">↕</button>` : ""}<span class="row-order">${html(row.display_order)}</span>`;
  const restore = row.is_draft === "true" && row.draft_edge_id
    ? `<button class="link-button" data-action="restore-draft" data-edge-id="${html(row.draft_edge_id)}" type="button">恢复</button>`
    : `<span class="${badgeClass(row.risk_level)}">${html(row.risk_level)}</span>`;
  const relationBadge = row.relation_type && row.relation_type !== "gb_bill"
    ? `<span class="${badgeClass(row.relation_type)}">${html(row.relation_type)}</span>`
    : "";
  return `
    <tr class="row-${html(row.row_type)}${active}" data-row-id="${html(row.row_id)}" ${isBill ? `data-drop-bill="${html(row.bill_code_9)}" data-bill-name="${html(row.bill_name)}"` : ""}>
      <td class="sticky-col">${expander}</td>
      <td><span class="${badgeClass(row.row_type)}">${rowLabel(row)}</span></td>
      <td><button class="link-button" data-action="select-row" data-row-id="${html(row.row_id)}" type="button">${html(row.quota_source_code || row.bill_code_9)}</button></td>
      <td class="text-clip" title="${html(row.quota_name_from_pdf || row.bill_name)}">${html(row.quota_name_from_pdf || row.bill_name)}</td>
      <td>${html(row.quota_unit_normalized)}</td>
      <td class="num">${html(row.labor_fee)}</td>
      <td class="num">${html(row.material_fee)}</td>
      <td class="num">${html(row.machine_fee)}</td>
      <td class="num">${html(row.management_fee)}</td>
      <td class="num">${html(row.base_price)}</td>
      <td>${relationBadge || `<span class="${badgeClass(row.mapping_role)}">${html(row.mapping_role)}</span>`}</td>
      <td><span class="${badgeClass(row.coverage_status)}">${html(row.coverage_status)}</span></td>
      <td><span class="${badgeClass(row.review_status)}">${html(row.review_status)}</span></td>
      <td>${restore}</td>
    </tr>
  `;
}

async function selectRow(row) {
  if (!row) return;
  state.activeRow = row;
  state.activeQuotaCode = row.row_type !== "gb_bill" && row.quota_source_code ? row.quota_source_code : "";
  state.activeDetail = null;
  state.quantityRuleView = "original";
  if (state.activeQuotaCode) {
    try {
      const detail = await api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/detail`);
      state.activeDetail = detail.detail;
    } catch {
      state.activeDetail = null;
    }
  }
  renderMainRows();
  renderDetails();
  await renderActiveTab();
}

function detailGrid(row, fields) {
  if (!row) return `<div class="detail-value">—</div>`;
  return fields
    .map(([label, key]) => `<div class="detail-label">${html(label)}</div><div class="detail-value">${html(row[key])}</div>`)
    .join("");
}

function renderDetails() {
  el.selectedDetails.innerHTML = detailGrid(state.activeRow, SELECTED_FIELDS);
  el.pdfDetails.innerHTML = detailGrid(state.activeDetail, PDF_FIELDS);
}

function setActiveTab(tab) {
  state.activeTab = tab;
  el.tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  renderActiveTab();
}

async function renderActiveTab() {
  if (!state.activeRow) {
    el.tabContent.textContent = "请选择 A1-1-* 省定额候选。";
    return;
  }
  if (state.activeRow.row_type === "gb_bill") {
    el.tabMeta.textContent = `${state.activeRow.bill_code_9} ${state.activeRow.bill_name || ""}`;
    el.tabContent.innerHTML = `<div class="detail-grid">${detailGrid({
      code: state.activeRow.bill_code_9,
      name: state.activeRow.bill_name,
      unit: state.activeRow.quota_unit_normalized,
      note: "当前选中 GB/T 清单行；可将 A1-1-* 候选关系拖放到该行生成草稿 overlay。",
    }, [
      ["清单编码", "code"],
      ["清单名称", "name"],
      ["计量单位", "unit"],
      ["说明", "note"],
    ])}</div>`;
    return;
  }
  if (state.activeRow.row_type === "xlsx_only_supplemental" || !state.activeDetail) {
    renderSupplementalIssue();
    return;
  }
  el.tabMeta.textContent = `${state.activeQuotaCode} ${state.activeDetail?.quota_name_from_pdf || ""}`;
  if (state.activeTab === "resources") {
    const data = await api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/resources`);
    renderResources(data.items || [], data);
  } else if (state.activeTab === "work_content") {
    const data = await api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/work-content`);
    renderWorkContent(data);
  } else if (state.activeTab === "quantity_rule") {
    const [sourcePages, structured] = await Promise.all([
      api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/quantity-rule/source-pages`),
      api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/quantity-rule/structured`),
    ]);
    renderQuantityRuleDualView(sourcePages, structured);
  } else if (state.activeTab === "reconciliation") {
    const data = await api(`/api/quota-a111/quota/${encodeURIComponent(state.activeQuotaCode)}/reconciliation`);
    el.tabContent.innerHTML = `<div class="detail-grid">${detailGrid(data, [
      ["PDF 页码", "pdf_page_no"],
      ["书内页码", "book_page_no"],
      ["XLSX 对账", "match_status"],
      ["价差", "delta_total"],
      ["覆盖状态", "coverage_status"],
      ["资源对账", "resource_reconciliation_status"],
      ["review", "review_status"],
    ])}</div>`;
  } else {
    el.tabContent.innerHTML = `<div class="detail-grid">${detailGrid({
      coverage_status: state.activeDetail?.coverage_status,
      high_issue: state.activeDetail?.has_high_or_blocking_issue,
      review_status: state.activeDetail?.review_status,
      note: "PDF 候选、工作内容、工程量规则和 XLSX 对账均为 pending review，不生成 approved。草稿关系也不等于正式 mapping。",
    }, [
      ["覆盖状态", "coverage_status"],
      ["高风险", "high_issue"],
      ["review", "review_status"],
      ["说明", "note"],
    ])}</div>`;
  }
}

function renderWorkContent(data) {
  const items = data.items || [];
  if (!items.length) {
    el.tabContent.innerHTML = `<div class="empty-row">当前定额没有可展示的工作内容。</div>`;
    return;
  }
  el.tabContent.innerHTML = `
    <div class="structured-detail-shell work-content-shell">
      <div class="structured-detail-meta">
        <span>展示项 ${html(items.length)}</span>
        <span>raw fallback ${html(data.raw_fallback_count || 0)}</span>
        <span>display only / pending review</span>
      </div>
      <div class="structured-table-scroll work-content-scroll">
        <table class="structured-detail-table work-content-table">
          <thead><tr><th>序号</th><th>工作内容</th><th>拆分</th><th>置信度</th></tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${html(item.item_no || item.item_order)}</td>
                <td class="long-text-cell">${html(item.item_text)}</td>
                <td><span class="${badgeClass(item.display_status)}">${html(item.split_method)}</span></td>
                <td class="num">${html(item.split_confidence)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <details class="raw-source-disclosure">
        <summary>查看原文</summary>
        <div class="raw-source-text">${html(data.raw_text)}</div>
      </details>
    </div>
  `;
}

function ruleSummary(value, maxLength = 84) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function renderQuantityRuleDualView(sourcePages, structured) {
  state.quantityRulePages = sourcePages.pages || [];
  state.quantityRuleBlocks = structured.items || [];
  state.quantityRulePageIndex = 0;
  state.selectedRuleBlockId = state.quantityRuleBlocks[0]?.rule_block_id || "";
  if (!state.quantityRulePages.length) {
    el.tabContent.innerHTML = `<div class="empty-row">原始工程量规则页不可用。</div>`;
    return;
  }
  el.tabContent.innerHTML = `
    <div class="rule-dual-shell">
      <div class="rule-subview-bar">
        <div class="rule-subview-tabs" role="tablist" aria-label="工程量规则视图">
          <button class="rule-subview-button" data-rule-view="original" type="button">原文视图</button>
          <button class="rule-subview-button" data-rule-view="structured" type="button">结构化视图</button>
          <button class="rule-subview-button" data-rule-view="comparison" type="button">对照视图</button>
        </div>
        <span class="rule-evidence-note">PDF 证据 ${html(state.quantityRulePages.length)} 页 / 唯一规则块 ${html(state.quantityRuleBlocks.length)} / scope pending</span>
      </div>
      <div id="ruleSubviewContent" class="rule-subview-content"></div>
    </div>
  `;
  el.tabContent.querySelectorAll("[data-rule-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.quantityRuleView = button.dataset.ruleView;
      renderQuantityRuleSubview();
    });
  });
  renderQuantityRuleSubview();
}

function currentQuantityRulePage() {
  return state.quantityRulePages[state.quantityRulePageIndex] || state.quantityRulePages[0];
}

function quantityRulePdfUrl(page) {
  const zoom = state.quantityRuleZoom === "page-width" ? "page-width" : String(state.quantityRuleZoom);
  return `/api/quota-a111/quantity-rule/source-pdf#page=${page.pdf_page_no}&zoom=${encodeURIComponent(zoom)}`;
}

function renderQuantityRuleSubview() {
  el.tabContent.querySelectorAll("[data-rule-view]").forEach((button) => {
    const active = button.dataset.ruleView === state.quantityRuleView;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  if (state.quantityRuleView === "structured") renderStructuredRuleView();
  else if (state.quantityRuleView === "comparison") renderComparisonRuleView();
  else renderOriginalRuleView();
}

function rulePdfControls() {
  const page = currentQuantityRulePage();
  const zoomLabel = state.quantityRuleZoom === "page-width" ? "适应宽度" : `${state.quantityRuleZoom}%`;
  return `
    <div class="rule-pdf-toolbar">
      <button class="icon-button" data-rule-page-action="prev" type="button" title="上一页" aria-label="上一页" ${state.quantityRulePageIndex <= 0 ? "disabled" : ""}>←</button>
      <button class="icon-button" data-rule-page-action="next" type="button" title="下一页" aria-label="下一页" ${state.quantityRulePageIndex >= state.quantityRulePages.length - 1 ? "disabled" : ""}>→</button>
      <span class="rule-page-label">PDF ${html(page.pdf_page_no)} / 书内 ${html(page.book_page_no)}</span>
      <button class="icon-button" data-rule-page-action="fit" type="button" title="适应宽度" aria-label="适应宽度">↔</button>
      <button class="icon-button" data-rule-page-action="zoom-out" type="button" title="缩小" aria-label="缩小">−</button>
      <button class="icon-button" data-rule-page-action="zoom-in" type="button" title="放大" aria-label="放大">+</button>
      <span class="rule-zoom-label">${html(zoomLabel)}</span>
    </div>
  `;
}

function renderOriginalRuleView() {
  const page = currentQuantityRulePage();
  const content = el.tabContent.querySelector("#ruleSubviewContent");
  content.innerHTML = `
    <section class="rule-original-view">
      ${rulePdfControls()}
      <div class="rule-page-context">
        <span>原始 PDF 页面</span>
        <span>表格：保留 PDF 原结构</span>
        <span>水印：保留</span>
        <span>规则块 ${html(page.rule_block_ids?.length || 0)}</span>
      </div>
      <iframe id="rulePdfFrame" class="rule-pdf-frame" title="省定额工程量规则原始 PDF 页" src="${html(quantityRulePdfUrl(page))}"></iframe>
    </section>
  `;
  bindRulePdfControls();
}

function structuredRuleTable(mode = "structured") {
  return `
    <div class="rule-structured-scroll structured-table-scroll">
      <table class="structured-detail-table rule-block-table">
        <thead><tr><th>规则号</th><th>层级</th><th>标题 / 摘要</th><th>适用范围</th><th>PDF 页</th></tr></thead>
        <tbody>
          ${state.quantityRuleBlocks.map((block) => `
            <tr class="rule-block-row${block.rule_block_id === state.selectedRuleBlockId ? " active" : ""}" data-rule-block-id="${html(block.rule_block_id)}" data-rule-mode="${html(mode)}" tabindex="0">
              <td>${html(block.rule_no)}</td>
              <td><span class="badge">${html(block.rule_level)}</span></td>
              <td class="long-text-cell"><strong>${html(block.rule_title)}</strong><br /><span>${html(block.rule_summary)}</span></td>
              <td><span class="${block.rule_scope === "uncertain" ? "badge warn" : "badge ok"}">${html(block.rule_scope)}</span></td>
              <td>${html(block.pdf_page_no)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderStructuredRuleView() {
  const content = el.tabContent.querySelector("#ruleSubviewContent");
  content.innerHTML = `
    <section class="rule-structured-view">
      <div class="structured-detail-meta">
        <span>唯一规则块 ${html(state.quantityRuleBlocks.length)}</span>
        <span>点击规则跳转对应 PDF 页</span>
        <span>摘要不替代原文</span>
      </div>
      ${structuredRuleTable("structured")}
    </section>
  `;
  bindStructuredRuleRows();
}

function selectedRuleBlock() {
  return state.quantityRuleBlocks.find((block) => block.rule_block_id === state.selectedRuleBlockId) || state.quantityRuleBlocks[0];
}

function renderRuleApplicability(block) {
  if (!block) return "";
  return `
    <div class="rule-applicability-panel">
      <strong>${html(block.rule_no)} ${html(block.rule_title)}</strong>
      <div class="detail-grid">
        ${detailGrid(block, [
          ["rule_scope", "rule_scope"],
          ["适用章节", "applicable_section"],
          ["编码起点", "applicable_quota_code_start"],
          ["编码终点", "applicable_quota_code_end"],
          ["人工范围复核", "requires_manual_scope_review"],
          ["PDF 页", "pdf_page_no"],
          ["书内页", "book_page_no"],
          ["解析状态", "parse_status"],
        ])}
      </div>
      <p>无可靠 bbox，仅跳转原页，不伪造高亮。</p>
    </div>
  `;
}

function renderComparisonRuleView() {
  const page = currentQuantityRulePage();
  const content = el.tabContent.querySelector("#ruleSubviewContent");
  content.innerHTML = `
    <section class="rule-comparison-view">
      <div class="rule-comparison-index">
        ${structuredRuleTable("comparison")}
        ${renderRuleApplicability(selectedRuleBlock())}
      </div>
      <div class="rule-comparison-evidence">
        ${rulePdfControls()}
        <iframe id="rulePdfFrame" class="rule-pdf-frame" title="结构化规则对应原始 PDF 页" src="${html(quantityRulePdfUrl(page))}"></iframe>
      </div>
    </section>
  `;
  bindStructuredRuleRows();
  bindRulePdfControls();
}

function bindStructuredRuleRows() {
  el.tabContent.querySelectorAll("[data-rule-block-id]").forEach((row) => {
    const activate = () => activateStructuredBlock(row.dataset.ruleBlockId, row.dataset.ruleMode);
    row.addEventListener("click", activate);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") activate();
    });
  });
}

function activateStructuredBlock(ruleBlockId, mode) {
  const block = state.quantityRuleBlocks.find((item) => item.rule_block_id === ruleBlockId);
  if (!block) return;
  state.selectedRuleBlockId = ruleBlockId;
  const pageIndex = state.quantityRulePages.findIndex((page) => Number(page.pdf_page_no) === Number(block.pdf_page_no));
  if (pageIndex >= 0) state.quantityRulePageIndex = pageIndex;
  if (mode === "structured") state.quantityRuleView = "original";
  renderQuantityRuleSubview();
}

function bindRulePdfControls() {
  el.tabContent.querySelectorAll("[data-rule-page-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.rulePageAction;
      if (action === "prev") state.quantityRulePageIndex = Math.max(0, state.quantityRulePageIndex - 1);
      if (action === "next") state.quantityRulePageIndex = Math.min(state.quantityRulePages.length - 1, state.quantityRulePageIndex + 1);
      if (action === "fit") state.quantityRuleZoom = "page-width";
      if (action === "zoom-in") state.quantityRuleZoom = Math.min(200, (Number(state.quantityRuleZoom) || 100) + 20);
      if (action === "zoom-out") state.quantityRuleZoom = Math.max(60, (Number(state.quantityRuleZoom) || 100) - 20);
      renderQuantityRuleSubview();
    });
  });
}

function renderSupplementalIssue() {
  el.tabMeta.textContent = `${state.activeRow.quota_source_code} supplemental / draft`;
  el.pdfDetails.innerHTML = detailGrid({
    coverage_status: state.activeRow.coverage_status,
    review_status: state.activeRow.review_status,
    has_high_or_blocking_issue: "manual_check_required",
  }, PDF_FIELDS);
  el.tabContent.innerHTML = `<div class="detail-grid">${detailGrid({
    code: state.activeRow.quota_source_code,
    name: state.activeRow.quota_name_from_pdf,
    coverage: state.activeRow.coverage_status,
    relation: state.activeRow.relation_type,
    note: "该行只作为草稿候选关系展示；不修改省定额本体，不生成 approved。",
  }, [
    ["编码", "code"],
    ["名称", "name"],
    ["覆盖状态", "coverage"],
    ["关系类型", "relation"],
    ["说明", "note"],
  ])}</div>`;
}

function renderResources(rows, meta) {
  if (!rows.length) {
    el.tabContent.innerHTML = `<div class="empty-row">当前定额没有资源明细。</div>`;
    return;
  }
  el.tabContent.innerHTML = `
    <table class="resource-table">
      <colgroup>
        <col class="col-index" />
        <col class="col-type" />
        <col class="col-code" />
        <col class="col-name" />
        <col class="col-name" />
        <col class="col-unit" />
        <col class="col-money" />
        <col class="col-money" />
        <col class="col-money" />
        <col class="col-status" />
        <col class="col-risk" />
      </colgroup>
      <thead>
        <tr>
          <th>序</th>
          <th>类别</th>
          <th>资源编码</th>
          <th>名称</th>
          <th>规格</th>
          <th>单位</th>
          <th>消耗量</th>
          <th>单价</th>
          <th>费用</th>
          <th>置信度</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${html(row.resource_display_order)}</td>
            <td>${html(row.resource_category_normalized)}</td>
            <td>${html(row.resource_code)}</td>
            <td class="text-clip" title="${html(row.resource_name)}">${html(row.resource_name)}</td>
            <td class="text-clip" title="${html(row.resource_spec)}">${html(row.resource_spec)}</td>
            <td>${html(row.resource_unit_normalized)}</td>
            <td class="num">${html(row.resource_consumption)}</td>
            <td class="num">${html(row.resource_unit_price)}</td>
            <td class="num">${html(row.resource_fee_calculated)}</td>
            <td>${html(row.parse_confidence)}</td>
            <td class="text-clip" title="${html(row.remark)}">${html(row.remark)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
    <div class="tab-text">当前定额资源 ${rows.length} 行；全量资源 ${meta.total_resource_row_count} 行。</div>
  `;
}

function draftPayloadFromRow(row) {
  return {
    source_edge_id: row.source_edge_id || row.row_id,
    source_bill_code_9: row.bill_code_9,
    source_bill_name: row.bill_name || "",
    quota_source_code: row.quota_source_code,
    quota_name: row.quota_name_from_pdf || "",
  };
}

function handleDragOver(event, target) {
  if (!state.dragPayload) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
  target.classList.add("drop-hover");
}

function handleDropToBill(event, targetBillCode, targetBillName) {
  event.preventDefault();
  document.querySelectorAll(".drop-hover").forEach((item) => item.classList.remove("drop-hover"));
  if (!state.dragPayload || !targetBillCode) return;
  openDraftModal(targetBillCode, targetBillName);
}

function openDraftModal(targetBillCode, targetBillName) {
  const payload = {
    ...state.dragPayload,
    target_bill_code_9: targetBillCode,
    target_bill_name: targetBillName,
    action_type: "copy_link",
    operation_reason: "",
    reviewer: "",
  };
  state.pendingDraft = payload;
  localStorage.setItem(STORAGE_PENDING_DRAFT, JSON.stringify(payload));
  el.modalQuotaCode.textContent = payload.quota_source_code;
  el.modalQuotaName.textContent = payload.quota_name || "—";
  el.modalSourceBill.textContent = `${payload.source_bill_code_9} ${payload.source_bill_name || ""}`;
  el.modalTargetBill.textContent = `${payload.target_bill_code_9} ${payload.target_bill_name || ""}`;
  el.draftReasonInput.value = payload.operation_reason || "";
  el.draftModal.classList.remove("hidden");
  showMessage("已生成待确认草稿 payload。请选择 Copy / Move / Exclude。");
}

function closeDraftModal(discard = false) {
  el.draftModal.classList.add("hidden");
  if (discard) {
    state.pendingDraft = null;
    localStorage.removeItem(STORAGE_PENDING_DRAFT);
  }
}

async function submitDraft(actionType) {
  if (!state.pendingDraft) return;
  const payload = {
    ...state.pendingDraft,
    action_type: actionType,
    operation_reason: el.draftReasonInput.value.trim(),
  };
  try {
    const result = await postApi("/api/quota-a111/draft/edge", payload);
    updateDraftStats(result.stats || {});
    localStorage.removeItem(STORAGE_PENDING_DRAFT);
    closeDraftModal(false);
    const nextBill = actionType === "exclude_link" ? payload.source_bill_code_9 : payload.target_bill_code_9;
    await refreshTree();
    await selectBill(nextBill, payload.quota_source_code);
    showMessage(`${actionType} 已写入本地草稿 SQLite；仍为 pending，未 approved。`);
  } catch (error) {
    showMessage(`保存失败：${error.message}`, true);
  }
}

async function restoreDraft(draftEdgeId) {
  if (!draftEdgeId) return;
  try {
    const result = await postApi(`/api/quota-a111/draft/edge/${encodeURIComponent(draftEdgeId)}/revert`, {});
    updateDraftStats(result.stats || {});
    await refreshTree();
    await selectBill(state.selectedBillCode);
    showMessage("已恢复原始候选显示；草稿 edge 标记为 reverted。");
  } catch (error) {
    showMessage(`恢复失败：${error.message}`, true);
  }
}

async function runSearch() {
  const query = el.treeSearchInput.value.trim();
  renderTree();
  if (!query) {
    el.searchResults.classList.remove("active");
    el.searchResults.innerHTML = "";
    return;
  }
  const data = await api(`/api/quota-a111/search?q=${encodeURIComponent(query)}`);
  const items = [
    ...(data.bills || []).map((row) => ({ type: "bill", label: `${row.bill_code_9} ${row.bill_name}`, bill: row.bill_code_9 })),
    ...(data.quotas || []).map((row) => ({ type: "quota", label: `${row.quota_source_code} ${row.quota_name_from_pdf}`, bill: row.bill_code_9, quota: row.quota_source_code })),
  ].slice(0, 30);
  if (!items.length) {
    el.searchResults.classList.add("active");
    el.searchResults.innerHTML = `<div class="search-result">无匹配结果</div>`;
    return;
  }
  el.searchResults.classList.add("active");
  el.searchResults.innerHTML = items.map((item, index) => `
    <button class="search-result" data-index="${index}" type="button">${html(item.type)} · ${html(item.label)}</button>
  `).join("");
  document.querySelectorAll(".search-result[data-index]").forEach((button) => {
    button.addEventListener("click", async () => {
      const item = items[Number(button.dataset.index)];
      if (item.bill) await selectBill(item.bill, item.quota || "");
    });
  });
}

function initResize() {
  const root = document.documentElement;
  root.style.setProperty("--left-width", localStorage.getItem("quota_a111_left_width") || "300px");
  root.style.setProperty("--right-width", localStorage.getItem("quota_a111_right_width") || "360px");
  root.style.setProperty("--bottom-height", localStorage.getItem("quota_a111_bottom_height") || "260px");

  const bindVertical = (splitter, side) => {
    splitter.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const startLeft = parseInt(getComputedStyle(root).getPropertyValue("--left-width"), 10) || 300;
      const startRight = parseInt(getComputedStyle(root).getPropertyValue("--right-width"), 10) || 360;
      const move = (moveEvent) => {
        const delta = moveEvent.clientX - startX;
        if (side === "left") {
          const next = Math.max(240, Math.min(560, startLeft + delta));
          root.style.setProperty("--left-width", `${next}px`);
          localStorage.setItem("quota_a111_left_width", `${next}px`);
        } else {
          const next = Math.max(300, Math.min(640, startRight - delta));
          root.style.setProperty("--right-width", `${next}px`);
          localStorage.setItem("quota_a111_right_width", `${next}px`);
        }
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  };

  el.bottomSplitter.addEventListener("mousedown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const start = parseInt(getComputedStyle(root).getPropertyValue("--bottom-height"), 10) || 260;
    const move = (moveEvent) => {
      const max = Math.floor(el.workspace.getBoundingClientRect().height * 0.55);
      const next = Math.max(170, Math.min(max, start - (moveEvent.clientY - startY)));
      root.style.setProperty("--bottom-height", `${next}px`);
      localStorage.setItem("quota_a111_bottom_height", `${next}px`);
    };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  });

  bindVertical(el.leftSplitter, "left");
  bindVertical(el.rightSplitter, "right");
}

function bindEvents() {
  el.treeSearchInput.addEventListener("input", () => {
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(runSearch, 180);
  });
  el.collapseBtn.addEventListener("click", () => {
    state.expandedBills.delete(state.selectedBillCode);
    persistExpanded();
    renderMainRows();
  });
  el.expandBtn.addEventListener("click", () => {
    state.expandedBills.add(state.selectedBillCode);
    persistExpanded();
    renderMainRows();
  });
  el.showExcludedToggle.addEventListener("change", async () => {
    state.showExcluded = el.showExcludedToggle.checked;
    await selectBill(state.selectedBillCode);
  });
  el.exportDraftBtn.addEventListener("click", async () => {
    try {
      const result = await api("/api/quota-a111/draft/export");
      showMessage(`草稿 CSV 已导出：${result.count} 行。${result.path}`);
    } catch (error) {
      showMessage(`导出草稿失败：${error.message}`, true);
    }
  });
  el.exportAuditBtn.addEventListener("click", async () => {
    try {
      const result = await api("/api/quota-a111/draft/audit/export");
      showMessage(`audit CSV 已导出：${result.count} 行。${result.path}`);
    } catch (error) {
      showMessage(`导出 audit 失败：${error.message}`, true);
    }
  });
  el.resetDraftBtn.addEventListener("click", async () => {
    if (!window.confirm("确认清空 /quota-a111 本地测试草稿？原始映射不会被修改。")) return;
    if (!window.confirm("二次确认：仅清空 web_quota_a111_mapping_draft_* 测试数据。")) return;
    try {
      const result = await postApi("/api/quota-a111/draft/reset-test-data", {});
      updateDraftStats({ total_count: 0, copy_count: 0, move_count: 0, exclude_count: 0, reverted_count: 0 });
      await refreshTree();
      await selectBill(state.selectedBillCode);
      showMessage(`已清空测试草稿：edge ${result.deleted_edges} / audit ${result.deleted_audit_rows}`);
    } catch (error) {
      showMessage(`清空失败：${error.message}`, true);
    }
  });
  el.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
  });
  el.confirmCopyBtn.addEventListener("click", () => submitDraft("copy_link"));
  el.confirmMoveBtn.addEventListener("click", () => submitDraft("move_link"));
  el.confirmExcludeBtn.addEventListener("click", () => submitDraft("exclude_link"));
  el.cancelDraftBtn.addEventListener("click", () => closeDraftModal(true));
  el.cancelDraftBtn2.addEventListener("click", () => closeDraftModal(true));
}

function restorePendingDraftIfNeeded() {
  const cached = localStorage.getItem(STORAGE_PENDING_DRAFT);
  if (!cached) return;
  try {
    const payload = JSON.parse(cached);
    if (!payload?.quota_source_code || !payload?.target_bill_code_9) {
      localStorage.removeItem(STORAGE_PENDING_DRAFT);
      return;
    }
    if (window.confirm("检测到上次未提交的候选关系草稿，是否恢复确认弹窗？")) {
      state.dragPayload = {
        source_edge_id: payload.source_edge_id,
        source_bill_code_9: payload.source_bill_code_9,
        source_bill_name: payload.source_bill_name,
        quota_source_code: payload.quota_source_code,
        quota_name: payload.quota_name,
      };
      openDraftModal(payload.target_bill_code_9, payload.target_bill_name || "");
    } else {
      localStorage.removeItem(STORAGE_PENDING_DRAFT);
    }
  } catch {
    localStorage.removeItem(STORAGE_PENDING_DRAFT);
  }
}

async function init() {
  initResize();
  bindEvents();
  const tree = await refreshTree();
  const firstBill = state.treeRows.find((row) => row.node_type === "bill" && Number(row.candidate_quota_count || 0) > 0);
  if (firstBill) await selectBill(firstBill.bill_code_9);
  restorePendingDraftIfNeeded();
}

init().catch((error) => {
  console.error(error);
  el.treeRoot.innerHTML = `<div class="empty-row">加载失败：${html(error.message)}</div>`;
  el.mainRows.innerHTML = `<tr><td colspan="14" class="empty-row">加载失败：${html(error.message)}</td></tr>`;
  showMessage(`加载失败：${error.message}`, true);
});
