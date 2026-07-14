const state = {
  treeItems: [],
  treeNodes: [],
  sourceFilters: [],
  nodeById: new Map(),
  selectedBillCode: "",
  selectedBill: null,
  compositionRows: [],
  activeRow: null,
  activeItemId: "",
  activeConsistency: null,
  showAllCandidates: false,
  sourceFile: localStorage.getItem("bid_collab_source_file") || "",
  sourceSection: localStorage.getItem("bid_collab_source_section") || "",
  itemQuery: "",
  expandedBidItems: new Set(JSON.parse(localStorage.getItem("bid_collab_standard_expanded_bid_items") || "[]")),
  expandedNodeIds: new Set(JSON.parse(localStorage.getItem("bid_collab_standard_expanded_nodes") || "[]")),
};

const el = {
  workspace: document.querySelector("#bidWorkspace"),
  summaryPill: document.querySelector("#summaryPill"),
  treeRoot: document.querySelector("#treeRoot"),
  treeCount: document.querySelector("#treeCount"),
  treeSearchInput: document.querySelector("#treeSearchInput"),
  sourceFilterCount: document.querySelector("#sourceFilterCount"),
  sourceFileFilter: document.querySelector("#sourceFileFilter"),
  sourceSectionFilter: document.querySelector("#sourceSectionFilter"),
  itemSearchInput: document.querySelector("#itemSearchInput"),
  listTitle: document.querySelector("#listTitle"),
  listMeta: document.querySelector("#listMeta"),
  compositionRows: document.querySelector("#compositionRows"),
  rowDetails: document.querySelector("#rowDetails"),
  consistencyDetails: document.querySelector("#consistencyDetails"),
  featureDetails: document.querySelector("#featureDetails"),
  candidateRows: document.querySelector("#candidateRows"),
  candidateMeta: document.querySelector("#candidateMeta"),
  leftSplitter: document.querySelector("#leftSplitter"),
  rightSplitter: document.querySelector("#rightSplitter"),
  bottomSplitter: document.querySelector("#bottomSplitter"),
  collapseAllBtn: document.querySelector("#collapseAllBtn"),
  expandAllBtn: document.querySelector("#expandAllBtn"),
  topCandidatesBtn: document.querySelector("#topCandidatesBtn"),
  allCandidatesBtn: document.querySelector("#allCandidatesBtn"),
  groupFilter: document.querySelector("#groupFilter"),
  typeFilter: document.querySelector("#typeFilter"),
  riskFilter: document.querySelector("#riskFilter"),
};

const ROW_DETAIL_FIELDS = [
  ["行类型", "row_type"],
  ["GB/T bill_code_9", "bill_code_9"],
  ["GB/T 清单名称", "gb_bill_name"],
  ["投标 Item Code", "raw_item_code"],
  ["规范化 Item Code", "normalized_item_code"],
  ["投标清单名称", "bid_item_name"],
  ["定额编码", "quota_source_code"],
  ["定额名称", "quota_name_candidate"],
  ["补子目编码", "supplement_candidate_code"],
  ["补子目名称", "supplement_name"],
  ["单位", "unit"],
  ["工程量", "quantity"],
  ["省定额价", "province_total_fee"],
  ["企业候选价", "enterprise_total_fee_candidate"],
  ["来源", "source_project_section"],
  ["匹配角色", "governance_role"],
  ["候选分组", "candidate_group"],
  ["默认显示", "default_visibility"],
  ["风险", "risk_flags"],
];

const CONSISTENCY_FIELDS = [
  ["状态", "consistency_status"],
  ["问题类型", "issue_type"],
  ["建议动作", "suggested_action"],
  ["投标名称", "bid_item_name"],
  ["GB/T 名称", "gb_bill_name"],
  ["备注", "remark"],
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

async function api(path) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

function badgeClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("conflict") || text.includes("failed") || text.includes("high") || text.includes("manual") || text.includes("unmatched")) return "badge danger";
  if (text.includes("minor") || text.includes("medium") || text.includes("collapsed") || text.includes("review")) return "badge warn";
  if (text.includes("consistent") || text.includes("r1") || text.includes("direct") || text.includes("show_in")) return "badge ok";
  return "badge neutral";
}

function persistTree() {
  localStorage.setItem("bid_collab_standard_expanded_nodes", JSON.stringify([...state.expandedNodeIds]));
}

function persistRows() {
  localStorage.setItem("bid_collab_standard_expanded_bid_items", JSON.stringify([...state.expandedBidItems]));
}

function buildTree(items) {
  const byId = new Map();
  const roots = [];
  items.forEach((item) => byId.set(item.node_id, { ...item, children: [] }));
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) byId.get(node.parent_id).children.push(node);
    else roots.push(node);
  });
  state.nodeById = byId;
  return roots;
}

function filterTree(nodes, query) {
  if (!query) return nodes;
  const q = query.toLowerCase();
  const visit = (node) => {
    const children = node.children.map(visit).filter(Boolean);
    const text = [node.label, node.bill_code_9, node.bill_name, node.appendix_name, node.section_name].join(" ").toLowerCase();
    if (text.includes(q) || children.length) return { ...node, children, forceOpen: true };
    return null;
  };
  return nodes.map(visit).filter(Boolean);
}

function renderTree() {
  const nodes = filterTree(state.treeNodes, el.treeSearchInput.value.trim());
  el.treeRoot.innerHTML = nodes.map(renderTreeNode).join("");
  document.querySelectorAll(".tree-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const node = button.closest(".tree-node");
      const nodeId = node.dataset.nodeId;
      if (node.dataset.type !== "bill") {
        if (state.expandedNodeIds.has(nodeId)) state.expandedNodeIds.delete(nodeId);
        else state.expandedNodeIds.add(nodeId);
        persistTree();
        renderTree();
        return;
      }
      await selectBill(node.dataset.bill);
    });
  });
}

function renderTreeNode(node) {
  const expanded = node.forceOpen || state.expandedNodeIds.has(node.node_id) ? " expanded" : "";
  const active = node.bill_code_9 && node.bill_code_9 === state.selectedBillCode ? " active" : "";
  const bidCount = Number(node.bid_item_count || 0);
  const conflictCount = Number(node.code_name_conflict_count || 0);
  const count = node.node_type === "bill" ? `${bidCount}${conflictCount ? ` / !${conflictCount}` : ""}` : `${node.gb_bill_count || 0} / ${bidCount}`;
  return `
    <div class="tree-node ${html(node.node_type)}${expanded}" data-node-id="${html(node.node_id)}" data-type="${html(node.node_type)}" data-bill="${html(node.bill_code_9)}">
      <button class="tree-button${active}" type="button">
        <span class="tree-caret">${node.children.length ? (expanded ? "▾" : "▸") : "•"}</span>
        <span class="tree-label" title="${html(node.tree_path || node.label)}">${html(node.label)}</span>
        <span class="${badgeClass(node.risk_level)}">${html(count)}</span>
      </button>
      ${node.children.length ? `<div class="tree-children">${node.children.map(renderTreeNode).join("")}</div>` : ""}
    </div>
  `;
}

function renderSourceFilters() {
  const projects = state.sourceFilters.filter((row) => row.node_type === "project");
  const sections = state.sourceFilters.filter((row) => row.node_type === "section" && (!state.sourceFile || row.source_file === state.sourceFile));
  el.sourceFilterCount.textContent = `${state.sourceFilters.length} 项`;
  el.sourceFileFilter.innerHTML = `<option value="">全部文件</option>${projects.map((row) => `<option value="${html(row.source_file)}">${html(row.label)} (${html(row.bid_item_count)})</option>`).join("")}`;
  el.sourceSectionFilter.innerHTML = `<option value="">全部分部</option>${sections.map((row) => `<option value="${html(row.section_name)}">${html(row.label)} (${html(row.bid_item_count)})</option>`).join("")}`;
  el.sourceFileFilter.value = state.sourceFile;
  el.sourceSectionFilter.value = state.sourceSection;
}

function billQuery() {
  const params = new URLSearchParams();
  if (state.sourceFile) params.set("source_file", state.sourceFile);
  if (state.sourceSection) params.set("section_name", state.sourceSection);
  if (state.itemQuery) params.set("q", state.itemQuery);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function visibleCompositionRows() {
  const rows = [];
  state.compositionRows.forEach((row) => {
    if (row.row_type === "gb_bill" || row.row_type === "bid_item") {
      rows.push(row);
      return;
    }
    if (state.expandedBidItems.has(row.bid_item_id)) rows.push(row);
  });
  return rows;
}

async function selectBill(billCode) {
  if (!billCode) return;
  state.selectedBillCode = billCode;
  const data = await api(`/api/bid/gb-bill/${encodeURIComponent(billCode)}/composition${billQuery()}`);
  state.compositionRows = data.rows || [];
  state.selectedBill = state.compositionRows.find((row) => row.row_type === "gb_bill") || null;
  state.compositionRows.filter((row) => row.row_type === "bid_item").forEach((row) => state.expandedBidItems.add(row.bid_item_id));
  persistRows();
  el.listTitle.textContent = `${billCode} ${state.selectedBill?.gb_bill_name || ""}`;
  el.listMeta.textContent = `投标清单 ${data.bid_item_count} / 组成行 ${data.count} / 推荐 ${data.recommended_row_count} / 候选池标记 ${data.candidate_pool_marker_count}`;
  renderTree();
  renderComposition();
  const firstItem = state.compositionRows.find((row) => row.row_type === "bid_item");
  await selectRow(firstItem || state.selectedBill);
}

function rowClass(row) {
  const parts = [`row-${row.row_type || ""}`];
  const status = row.code_name_consistency_status || row.risk_flags || "";
  if (String(status).includes("conflict") || String(status).includes("unmatched") || String(status).includes("high")) parts.push("row-conflict");
  return parts.join(" ");
}

function renderComposition() {
  const rows = visibleCompositionRows();
  if (!rows.length) {
    el.compositionRows.innerHTML = `<tr><td colspan="13" class="empty-row">当前国标清单下无投标清单实例</td></tr>`;
    return;
  }
  el.compositionRows.innerHTML = rows.map(renderCompositionRow).join("");
  document.querySelectorAll("[data-action='select-row']").forEach((button) => {
    button.addEventListener("click", () => {
      const row = state.compositionRows.find((item) => item.row_id === button.dataset.rowId);
      if (row) selectRow(row);
    });
  });
  document.querySelectorAll("[data-action='toggle-item']").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.itemId;
      if (state.expandedBidItems.has(id)) state.expandedBidItems.delete(id);
      else state.expandedBidItems.add(id);
      persistRows();
      renderComposition();
    });
  });
}

function levelLabel(row) {
  if (row.row_type === "gb_bill") return "GB";
  if (row.row_type === "bid_item") return "清单";
  if (row.row_type === "recommended_quota") return "定额";
  if (row.row_type === "recommended_supplement") return "补";
  if (row.row_type === "candidate_pool_marker" || row.row_type === "collapsed_candidate_pool_marker") return "池";
  return "警";
}

function renderCompositionRow(row) {
  const isBidItem = row.row_type === "bid_item";
  const expander = isBidItem
    ? `<button class="expander" data-action="toggle-item" data-item-id="${html(row.bid_item_id)}" type="button">${state.expandedBidItems.has(row.bid_item_id) ? "−" : "+"}</button>`
    : html(row.display_order);
  const indent = Number(row.display_level || 0);
  const displayCode = `<button class="link-button" data-action="select-row" data-row-id="${html(row.row_id)}" type="button">${html(row.display_code)}</button>`;
  const quotaCode = row.quota_source_code || row.supplement_candidate_code || "";
  const role = row.governance_role || row.default_visibility || row.matched_bill_status || "";
  const risk = row.risk_flags || row.recommendation_reason || row.code_name_consistency_status || "";
  return `
    <tr class="${rowClass(row)}">
      <td class="sticky-col">${expander}</td>
      <td><span class="level level-${html(row.row_type)}">${levelLabel(row)}</span></td>
      <td>${row.row_type === "gb_bill" ? displayCode : html(row.bill_code_9)}</td>
      <td>${row.row_type === "bid_item" ? displayCode : html(row.raw_item_code || row.normalized_item_code)}</td>
      <td>${row.row_type !== "gb_bill" && row.row_type !== "bid_item" ? displayCode : html(quotaCode)}</td>
      <td class="text-clip strong indent-${indent}" title="${html(row.display_name)}">${html(row.display_name)}</td>
      <td class="text-clip feature-cell" title="${html(row.project_feature_full)}">${html(row.project_feature_summary)}</td>
      <td>${html(row.unit)}</td>
      <td class="num">${html(row.quantity)}</td>
      <td class="num">${html(row.province_total_fee)}</td>
      <td class="num">${html(row.enterprise_total_fee_candidate)}</td>
      <td><span class="${badgeClass(role)}">${html(role)}</span></td>
      <td class="text-clip" title="${html(risk)}">${html(risk)}</td>
    </tr>
  `;
}

async function selectRow(row) {
  if (!row) return;
  state.activeRow = row;
  state.activeItemId = row.bid_item_id || "";
  state.activeConsistency = null;
  if (state.activeItemId) {
    try {
      const consistency = await api(`/api/bid/item/${encodeURIComponent(state.activeItemId)}/consistency`);
      state.activeConsistency = consistency.consistency;
    } catch {
      state.activeConsistency = null;
    }
    await loadCandidatePool();
  } else {
    renderEmptyCandidates("选择投标清单实例后显示候选池");
  }
  renderDetails();
}

function detailGrid(row, fields) {
  if (!row) return `<div class="detail-value">—</div>`;
  return fields
    .map(([label, key]) => `<div class="detail-label">${html(label)}</div><div class="detail-value">${html(row[key])}</div>`)
    .join("");
}

function renderDetails() {
  el.rowDetails.innerHTML = detailGrid(state.activeRow, ROW_DETAIL_FIELDS);
  el.consistencyDetails.innerHTML = detailGrid(state.activeConsistency, CONSISTENCY_FIELDS);
  el.featureDetails.textContent = state.activeRow?.project_feature_full || "—";
}

function candidateQuery() {
  const params = new URLSearchParams({
    show_all: state.showAllCandidates ? "true" : "false",
    candidate_group: el.groupFilter.value,
    candidate_type: el.typeFilter.value,
    risk: el.riskFilter.value,
  });
  return params.toString();
}

function renderEmptyCandidates(message) {
  el.candidateMeta.textContent = message;
  el.candidateRows.innerHTML = `<tr><td colspan="8" class="empty-row small">${html(message)}</td></tr>`;
}

async function loadCandidatePool() {
  if (!state.activeItemId) {
    renderEmptyCandidates("选择投标清单实例后显示候选池");
    return;
  }
  try {
    const data = await api(`/api/bid/item/${encodeURIComponent(state.activeItemId)}/candidate_pool?${candidateQuery()}`);
    renderCandidates(data);
  } catch {
    renderEmptyCandidates("当前清单没有候选池");
  }
}

function renderCandidates(data) {
  el.candidateMeta.textContent = `显示 ${data.count} / 筛选 ${data.filtered_count} / 总 ${data.total_count}，折叠 ${data.collapsed_count}，隐藏 ${data.hidden_count}`;
  const rows = data.items || [];
  if (!rows.length) {
    renderEmptyCandidates("当前筛选无候选");
    return;
  }
  el.candidateRows.innerHTML = rows.map((row) => `
    <tr class="${row.default_visibility === "show_in_composition_preview" ? "candidate-top" : ""}">
      <td>${html(row.candidate_rank)}</td>
      <td>${html(row.quota_source_code || "ENT-SUP")}</td>
      <td class="text-clip" title="${html(row.quota_name_candidate || row.bid_item_name)}">${html(row.quota_name_candidate || row.bid_item_name)}</td>
      <td><span class="${badgeClass(row.candidate_group)}">${html(row.candidate_group)}</span></td>
      <td class="num">${html(row.enterprise_total_fee_candidate)}</td>
      <td><span class="${badgeClass(row.default_visibility)}">${html(row.default_visibility)}</span></td>
      <td class="text-clip" title="${html(row.risk_flags)}">${html(row.risk_flags)}</td>
      <td class="text-clip" title="${html(row.recommendation_reason)}">${html(row.recommendation_reason)}</td>
    </tr>
  `).join("");
}

function findInitialBill() {
  return (
    state.treeItems.find((row) => row.node_type === "bill" && Number(row.bid_item_count || 0) > 0 && row.appendix_code !== "UNMATCHED")
    || state.treeItems.find((row) => row.node_type === "bill" && Number(row.bid_item_count || 0) > 0)
    || state.treeItems.find((row) => row.node_type === "bill")
  );
}

function initResize() {
  const sizes = {
    left: localStorage.getItem("bid_collab_left_width") || "300px",
    right: localStorage.getItem("bid_collab_right_width") || "380px",
    bottom: localStorage.getItem("bid_collab_bottom_height") || "230px",
  };
  document.documentElement.style.setProperty("--left-width", sizes.left);
  document.documentElement.style.setProperty("--right-width", sizes.right);
  document.documentElement.style.setProperty("--bottom-height", sizes.bottom);

  const bindVertical = (splitter, side) => {
    splitter.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const root = document.documentElement;
      const startLeft = parseInt(getComputedStyle(root).getPropertyValue("--left-width"), 10) || 300;
      const startRight = parseInt(getComputedStyle(root).getPropertyValue("--right-width"), 10) || 380;
      const move = (moveEvent) => {
        const delta = moveEvent.clientX - startX;
        if (side === "left") {
          const next = Math.max(240, Math.min(520, startLeft + delta));
          root.style.setProperty("--left-width", `${next}px`);
          localStorage.setItem("bid_collab_left_width", `${next}px`);
        } else {
          const next = Math.max(300, Math.min(640, startRight - delta));
          root.style.setProperty("--right-width", `${next}px`);
          localStorage.setItem("bid_collab_right_width", `${next}px`);
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
    const root = document.documentElement;
    const start = parseInt(getComputedStyle(root).getPropertyValue("--bottom-height"), 10) || 230;
    const move = (moveEvent) => {
      const workspaceHeight = el.workspace.getBoundingClientRect().height;
      const max = Math.floor(workspaceHeight * 0.45);
      const next = Math.max(150, Math.min(max, start - (moveEvent.clientY - startY)));
      root.style.setProperty("--bottom-height", `${next}px`);
      localStorage.setItem("bid_collab_bottom_height", `${next}px`);
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
  el.treeSearchInput.addEventListener("input", () => renderTree());
  el.itemSearchInput.addEventListener("input", () => {
    window.clearTimeout(state.itemSearchTimer);
    state.itemSearchTimer = window.setTimeout(async () => {
      state.itemQuery = el.itemSearchInput.value.trim();
      await selectBill(state.selectedBillCode);
    }, 180);
  });
  el.sourceFileFilter.addEventListener("change", async () => {
    state.sourceFile = el.sourceFileFilter.value;
    state.sourceSection = "";
    localStorage.setItem("bid_collab_source_file", state.sourceFile);
    localStorage.setItem("bid_collab_source_section", "");
    renderSourceFilters();
    await selectBill(state.selectedBillCode);
  });
  el.sourceSectionFilter.addEventListener("change", async () => {
    state.sourceSection = el.sourceSectionFilter.value;
    localStorage.setItem("bid_collab_source_section", state.sourceSection);
    await selectBill(state.selectedBillCode);
  });
  el.collapseAllBtn.addEventListener("click", () => {
    state.expandedBidItems.clear();
    persistRows();
    renderComposition();
  });
  el.expandAllBtn.addEventListener("click", () => {
    state.compositionRows.filter((row) => row.row_type === "bid_item").forEach((row) => state.expandedBidItems.add(row.bid_item_id));
    persistRows();
    renderComposition();
  });
  el.topCandidatesBtn.addEventListener("click", async () => {
    state.showAllCandidates = false;
    el.topCandidatesBtn.classList.replace("ghost-button", "primary-button");
    el.allCandidatesBtn.classList.replace("primary-button", "ghost-button");
    await loadCandidatePool();
  });
  el.allCandidatesBtn.addEventListener("click", async () => {
    state.showAllCandidates = true;
    el.allCandidatesBtn.classList.replace("ghost-button", "primary-button");
    el.topCandidatesBtn.classList.replace("primary-button", "ghost-button");
    await loadCandidatePool();
  });
  [el.groupFilter, el.typeFilter, el.riskFilter].forEach((select) => select.addEventListener("change", loadCandidatePool));
}

async function init() {
  initResize();
  bindEvents();
  const [tree, filters] = await Promise.all([
    api("/api/bid/gb-standard-tree"),
    api("/api/bid/source-filters"),
  ]);
  state.treeItems = tree.items || [];
  state.treeNodes = buildTree(state.treeItems);
  state.sourceFilters = filters.items || [];
  el.summaryPill.textContent = `${tree.gb_bill_count} GB bill / ${state.treeItems[0]?.bid_item_count || 0} 投标清单`;
  el.treeCount.textContent = `${tree.gb_bill_count} 条 GB/T bill`;
  renderSourceFilters();
  renderTree();
  const initial = findInitialBill();
  if (initial) await selectBill(initial.bill_code_9);
}

init().catch((error) => {
  console.error(error);
  el.treeRoot.innerHTML = `<div class="empty-row">加载失败：${html(error.message)}</div>`;
  el.compositionRows.innerHTML = `<tr><td colspan="13" class="empty-row">加载失败：${html(error.message)}</td></tr>`;
});
