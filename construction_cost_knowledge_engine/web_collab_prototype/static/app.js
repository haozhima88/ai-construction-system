const state = {
  treeItems: [],
  treeNodes: [],
  nodeById: new Map(),
  activeBill: null,
  activeRows: [],
  activeQuota: null,
  currentDraftRow: null,
  currentEditingKey: "",
  expandedNodeIds: new Set(JSON.parse(localStorage.getItem("web_collab_expanded_nodes") || "[]")),
  dirtyDrafts: new Set(),
  autosaveTimer: null,
  autosaveInterval: null,
  pendingRetry: null,
};

const el = {
  workspace: document.querySelector("#workspace"),
  treeRoot: document.querySelector("#treeRoot"),
  treeCount: document.querySelector("#treeCount"),
  searchInput: document.querySelector("#searchInput"),
  billTitle: document.querySelector("#billTitle"),
  billMeta: document.querySelector("#billMeta"),
  quotaRows: document.querySelector("#quotaRows"),
  billDetails: document.querySelector("#billDetails"),
  quotaDetails: document.querySelector("#quotaDetails"),
  saveStatus: document.querySelector("#saveStatus"),
  globalSaveState: document.querySelector("#globalSaveState"),
  exportDraftBtn: document.querySelector("#exportDraftBtn"),
  exportAuditBtn: document.querySelector("#exportAuditBtn"),
  retrySaveBtn: document.querySelector("#retrySaveBtn"),
  leftSplitter: document.querySelector("#leftSplitter"),
  rightSplitter: document.querySelector("#rightSplitter"),
  dialog: document.querySelector("#draftDialog"),
  closeDialogBtn: document.querySelector("#closeDialogBtn"),
  draftContext: document.querySelector("#draftContext"),
  dialogSaveState: document.querySelector("#dialogSaveState"),
  dialogVersion: document.querySelector("#dialogVersion"),
  dialogLastSaved: document.querySelector("#dialogLastSaved"),
  dialogCacheState: document.querySelector("#dialogCacheState"),
  draftLabor: document.querySelector("#draftLabor"),
  draftMaterial: document.querySelector("#draftMaterial"),
  draftMachine: document.querySelector("#draftMachine"),
  draftManagement: document.querySelector("#draftManagement"),
  draftTotal: document.querySelector("#draftTotal"),
  manualOverride: document.querySelector("#manualOverride"),
  draftComment: document.querySelector("#draftComment"),
  saveDraftBtn: document.querySelector("#saveDraftBtn"),
  useProvinceInDialogBtn: document.querySelector("#useProvinceInDialogBtn"),
};

const BILL_LABELS = [
  ["清单编码", "bill_code_9"],
  ["清单名称", "bill_name"],
  ["附录", "appendix_name"],
  ["章节", "section_name"],
  ["单位", "unit"],
  ["工程量计算规则", "quantity_calculation_rule"],
  ["工作内容", "work_content_raw"],
  ["项目特征", "project_feature_raw"],
  ["候选定额数量", "candidate_quota_count"],
  ["风险等级", "risk_level"],
];

const QUOTA_LABELS = [
  ["定额编码", "quota_source_code"],
  ["定额名称", "quota_name_candidate"],
  ["单位", "quota_display_unit"],
  ["省定额人工费", "province_labor_fee"],
  ["省定额材料费", "province_material_fee"],
  ["省定额机具费", "province_machine_fee"],
  ["省定额管理费", "province_management_fee"],
  ["省定额合计", "province_total_fee"],
  ["企业候选人工费", "enterprise_labor_fee_candidate"],
  ["企业候选材料费", "enterprise_material_fee_candidate"],
  ["企业候选机具费", "enterprise_machine_fee_candidate"],
  ["企业候选管理费", "enterprise_management_fee_candidate"],
  ["企业候选合计", "enterprise_total_fee_candidate"],
  ["企业候选单位", "enterprise_price_unit_candidate"],
  ["单位换算系数", "unit_conversion_factor"],
  ["单位换算说明", "unit_conversion_note"],
  ["草稿版本", "draft_version"],
  ["保存状态", "save_status"],
  ["最后保存", "last_saved_at"],
  ["治理角色", "governance_role"],
  ["风险标记", "risk_flags"],
];

function empty(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function rawNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return Number.isFinite(n) ? String(n) : "";
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function money(value) {
  const parsed = numberOrNull(value);
  if (parsed === null) return "—";
  return parsed.toFixed(2).replace(/\.00$/, "");
}

function html(value) {
  return empty(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function keyFor(billCode, quotaCode) {
  return `${billCode}::${quotaCode}`;
}

function cacheKeyFor(billCode, quotaCode) {
  return `web_collab_draft_cache::${billCode}::${quotaCode}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  return response.json();
}

function setStatus(message, kind = "muted") {
  el.saveStatus.textContent = message || "";
  el.globalSaveState.textContent = message || "未编辑";
  el.globalSaveState.classList.toggle("error", kind === "error");
  el.dialogSaveState.textContent = message || "未编辑";
}

function hasUnsavedDraft() {
  return state.dirtyDrafts.size > 0;
}

async function guardNavigation(action) {
  if (!hasUnsavedDraft()) {
    await action();
    return;
  }
  const choice = window.prompt("当前有未保存草稿，输入 1 保存并继续，2 放弃修改，3 取消操作。", "1");
  if (choice === "1") {
    const saved = await saveCurrentDraft("manual_enterprise_draft", "saved", false);
    if (saved) await action();
  } else if (choice === "2") {
    clearDirty(state.currentEditingKey);
    await action();
  }
}

function persistExpanded() {
  localStorage.setItem("web_collab_expanded_nodes", JSON.stringify([...state.expandedNodeIds]));
}

function buildTree(items) {
  const byId = new Map();
  const roots = [];
  items.forEach((item) => byId.set(item.node_id, { ...item, children: [] }));
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id).children.push(node);
    } else {
      roots.push(node);
    }
  });
  state.nodeById = byId;
  return roots;
}

function filterTree(nodes, query) {
  if (!query) return nodes;
  const q = query.toLowerCase();
  const filterNode = (node) => {
    const children = node.children.map(filterNode).filter(Boolean);
    const text = [node.label, node.bill_code_9, node.bill_name, node.section_name, node.appendix_name].join(" ").toLowerCase();
    if (text.includes(q) || children.length) return { ...node, children, forceOpen: true };
    return null;
  };
  return nodes.map(filterNode).filter(Boolean);
}

function ensureParentsExpanded(nodeId) {
  let node = state.nodeById.get(nodeId);
  while (node?.parent_id) {
    state.expandedNodeIds.add(node.parent_id);
    node = state.nodeById.get(node.parent_id);
  }
  persistExpanded();
}

function renderTree() {
  const query = el.searchInput.value.trim();
  const nodes = filterTree(state.treeNodes, query);
  el.treeRoot.innerHTML = nodes.map(renderTreeNode).join("");
  document.querySelectorAll(".tree-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const wrapper = button.closest(".tree-node");
      const type = wrapper.dataset.type;
      if (type === "bill") {
        await selectBill(wrapper.dataset.bill);
        return;
      }
      await guardNavigation(async () => {
        const nodeId = wrapper.dataset.nodeId;
        if (state.expandedNodeIds.has(nodeId)) state.expandedNodeIds.delete(nodeId);
        else state.expandedNodeIds.add(nodeId);
        persistExpanded();
        renderTree();
      });
    });
  });
}

function renderTreeNode(node) {
  const active = state.activeBill?.bill_code_9 === node.bill_code_9 ? " active" : "";
  const expanded = node.forceOpen || state.expandedNodeIds.has(node.node_id) ? " expanded" : "";
  const riskClassName = node.risk_level ? ` risk-${node.risk_level}` : "";
  const count = node.node_type === "bill" ? `${empty(node.candidate_quota_count)} 项` : `${empty(node.child_count)} / ${empty(node.candidate_quota_count)}`;
  return `
    <div class="tree-node ${node.node_type}${expanded}" data-node-id="${html(node.node_id)}" data-type="${html(node.node_type)}" data-bill="${html(node.bill_code_9)}">
      <button class="tree-button${active}" type="button">
        <span class="tree-caret">${node.node_type === "bill" ? "·" : "›"}</span>
        <span class="tree-label${riskClassName}" title="${html(node.label)}">${html(node.label)}</span>
        <span class="tree-count">${html(count)}</span>
      </button>
      ${node.children.length ? `<div class="tree-children">${node.children.map(renderTreeNode).join("")}</div>` : ""}
    </div>
  `;
}

async function selectBill(billCode, bypassGuard = false) {
  const run = async () => {
    if (!billCode) return;
    setStatus("加载清单候选定额...");
    const data = await api(`/api/bill/${encodeURIComponent(billCode)}/rows`);
    state.activeBill = data.bill;
    state.activeRows = data.rows || [];
    state.activeQuota = null;
    ensureParentsExpanded(`BILL-${billCode}`);
    renderTree();
    renderBill();
    renderRows();
    renderDetails();
    setStatus("");
  };
  if (bypassGuard) await run();
  else await guardNavigation(run);
}

function renderBill() {
  const bill = state.activeBill;
  el.billTitle.textContent = bill ? `${bill.bill_code_9} ${bill.bill_name}` : "请选择清单项";
  el.billMeta.textContent = bill ? `${empty(bill.appendix_name)} / ${empty(bill.section_name)} / 候选 ${empty(bill.candidate_quota_count)} 项` : "附录 / 章节 / 候选数量";
}

function renderRows() {
  if (!state.activeRows.length) {
    el.quotaRows.innerHTML = `<tr><td colspan="19" class="empty-row">当前清单项没有候选定额</td></tr>`;
    return;
  }
  el.quotaRows.innerHTML = state.activeRows.map(renderQuotaRow).join("");
  document.querySelectorAll("[data-action='detail']").forEach((button) => button.addEventListener("click", () => showQuotaDetail(button.dataset.quota)));
  document.querySelectorAll("[data-action='edit']").forEach((button) => button.addEventListener("click", () => openDraftDialog(button.dataset.quota)));
  document.querySelectorAll("[data-action='use-province']").forEach((button) => button.addEventListener("click", () => useProvincePrice(button.dataset.quota)));
  document.querySelectorAll("[data-action='clear']").forEach((button) => button.addEventListener("click", () => clearDraft(button.dataset.quota)));
}

function renderQuotaRow(row) {
  const selected = state.activeQuota?.quota_source_code === row.quota_source_code ? " selected" : "";
  const enterpriseStatus = row.draft_total_fee !== null && row.draft_total_fee !== undefined ? "已保存草稿" : empty(row.enterprise_price_status);
  const versionText = row.draft_version ? `v${row.draft_version} / ${empty(row.save_status)}` : "—";
  return `
    <tr class="${selected}">
      <td class="sticky-col code-col"><button class="link-button" type="button" data-action="detail" data-quota="${html(row.quota_source_code)}">${html(row.quota_source_code)}</button></td>
      <td class="sticky-col name-col second">${html(row.quota_name_candidate || row.quota_raw_name)}</td>
      <td>${html(row.quota_display_unit || row.quota_unit)}</td>
      <td>${html(money(row.province_labor_fee))}</td>
      <td>${html(money(row.province_material_fee))}</td>
      <td>${html(money(row.province_machine_fee))}</td>
      <td>${html(money(row.province_management_fee))}</td>
      <td>${html(money(row.province_total_fee))}</td>
      <td>${priceWithDraft(row.enterprise_labor_fee_candidate, row.draft_labor_fee)}</td>
      <td>${priceWithDraft(row.enterprise_material_fee_candidate, row.draft_material_fee)}</td>
      <td>${priceWithDraft(row.enterprise_machine_fee_candidate, row.draft_machine_fee)}</td>
      <td>${priceWithDraft(row.enterprise_management_fee_candidate, row.draft_management_fee)}</td>
      <td>${priceWithDraft(row.enterprise_total_fee_candidate, row.draft_total_fee)}</td>
      <td>${html(row.diff_total_rate)}</td>
      <td>${html(enterpriseStatus)}</td>
      <td>${html(versionText)}</td>
      <td>${html(row.governance_role)}</td>
      <td class="${riskClass(row.edge_risk_level)}">${html(row.risk_flags || row.issue_types || row.edge_risk_level)}</td>
      <td class="actions-col">
        <div class="row-actions">
          <button type="button" data-action="edit" data-quota="${html(row.quota_source_code)}">编辑企业价</button>
          <button type="button" data-action="use-province" data-quota="${html(row.quota_source_code)}">采用省定额价</button>
          <button type="button" data-action="clear" data-quota="${html(row.quota_source_code)}">清空草稿</button>
        </div>
      </td>
    </tr>
  `;
}

function priceWithDraft(candidate, draft) {
  const candidateText = html(money(candidate));
  if (draft === null || draft === undefined || draft === "") return candidateText;
  return `${candidateText}<span class="draft-badge">草稿 ${html(money(draft))}</span>`;
}

function riskClass(level) {
  if (level === "high") return "risk-high";
  if (level === "medium") return "risk-medium";
  if (level === "low") return "risk-low";
  return "";
}

async function showQuotaDetail(quotaCode) {
  await guardNavigation(async () => {
    state.activeQuota = state.activeRows.find((row) => row.quota_source_code === quotaCode) || null;
    renderRows();
    renderDetails();
  });
}

function renderDetails() {
  el.billDetails.innerHTML = state.activeBill ? detailGrid(state.activeBill, BILL_LABELS) : `<div class="detail-value">—</div>`;
  el.quotaDetails.innerHTML = state.activeQuota ? detailGrid(state.activeQuota, QUOTA_LABELS) : `<div class="detail-value">—</div>`;
}

function detailGrid(row, labels) {
  return labels.map(([label, key]) => `<div class="detail-label">${html(label)}</div><div class="detail-value">${html(empty(row[key]))}</div>`).join("");
}

function findRow(quotaCode) {
  return state.activeRows.find((row) => row.quota_source_code === quotaCode);
}

function readDraftInputs() {
  return {
    draft_labor_fee: numberOrNull(el.draftLabor.value),
    draft_material_fee: numberOrNull(el.draftMaterial.value),
    draft_machine_fee: numberOrNull(el.draftMachine.value),
    draft_management_fee: numberOrNull(el.draftManagement.value),
    draft_total_fee: numberOrNull(el.draftTotal.value),
    total_manual_override: el.manualOverride.checked,
    cost_engineer_comment: el.draftComment.value,
  };
}

function applyDraftInputs(values) {
  el.draftLabor.value = rawNumber(values.draft_labor_fee);
  el.draftMaterial.value = rawNumber(values.draft_material_fee);
  el.draftMachine.value = rawNumber(values.draft_machine_fee);
  el.draftManagement.value = rawNumber(values.draft_management_fee);
  el.draftTotal.value = rawNumber(values.draft_total_fee);
  el.manualOverride.checked = Boolean(values.total_manual_override);
  el.draftComment.value = values.cost_engineer_comment || "";
}

function localCachePayload() {
  return {
    ...readDraftInputs(),
    cached_at: new Date().toISOString(),
  };
}

function markDirty() {
  if (!state.currentEditingKey) return;
  state.dirtyDrafts.add(state.currentEditingKey);
  localStorage.setItem(cacheKeyFor(state.activeBill.bill_code_9, state.currentDraftRow.quota_source_code), JSON.stringify(localCachePayload()));
  el.dialogCacheState.textContent = "本地缓存 已更新";
  setStatus("未保存");
  scheduleAutosave();
}

function clearDirty(key) {
  if (!key) return;
  state.dirtyDrafts.delete(key);
  const [billCode, quotaCode] = key.split("::");
  localStorage.removeItem(cacheKeyFor(billCode, quotaCode));
  el.dialogCacheState.textContent = "本地缓存 已清除";
}

async function openDraftDialog(quotaCode) {
  await guardNavigation(async () => {
    const row = findRow(quotaCode);
    if (!row || !state.activeBill) return;
    state.currentDraftRow = row;
    state.currentEditingKey = keyFor(state.activeBill.bill_code_9, row.quota_source_code);
    state.activeQuota = row;
    renderDetails();
    el.draftContext.textContent = `${state.activeBill.bill_code_9} ${state.activeBill.bill_name} / ${row.quota_source_code} ${row.quota_name_candidate || row.quota_raw_name}`;
    applyDraftInputs({
      draft_labor_fee: row.draft_labor_fee ?? row.enterprise_labor_fee_candidate,
      draft_material_fee: row.draft_material_fee ?? row.enterprise_material_fee_candidate,
      draft_machine_fee: row.draft_machine_fee ?? row.enterprise_machine_fee_candidate,
      draft_management_fee: row.draft_management_fee ?? row.enterprise_management_fee_candidate,
      draft_total_fee: row.draft_total_fee ?? row.enterprise_total_fee_candidate,
      total_manual_override: row.total_manual_override,
      cost_engineer_comment: row.cost_engineer_comment,
    });
    el.dialogVersion.textContent = `版本 ${row.draft_version ? `v${row.draft_version}` : "-"}`;
    el.dialogLastSaved.textContent = `最后保存 ${empty(row.last_saved_at || row.draft_updated_at)}`;
    el.dialogCacheState.textContent = "本地缓存 -";
    const cacheRaw = localStorage.getItem(cacheKeyFor(state.activeBill.bill_code_9, row.quota_source_code));
    if (cacheRaw && window.confirm("发现本地未保存草稿，是否恢复？")) {
      applyDraftInputs(JSON.parse(cacheRaw));
      state.dirtyDrafts.add(state.currentEditingKey);
      el.dialogCacheState.textContent = "本地缓存 已恢复";
    }
    updateDraftTotal();
    startAutosaveInterval();
    el.dialog.showModal();
  });
}

function updateDraftTotal() {
  if (el.manualOverride.checked) return;
  const hasAny = [el.draftLabor, el.draftMaterial, el.draftMachine, el.draftManagement].some((input) => input.value !== "");
  if (!hasAny) return;
  const total = [el.draftLabor, el.draftMaterial, el.draftMachine, el.draftManagement]
    .map((input) => Number(input.value || 0))
    .reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
  el.draftTotal.value = total.toFixed(2);
}

function provinceValues(row) {
  const labor = numberOrNull(row.province_labor_fee);
  const material = numberOrNull(row.province_material_fee);
  const machine = numberOrNull(row.province_machine_fee);
  const management = numberOrNull(row.province_management_fee);
  const total = numberOrNull(row.province_total_fee);
  const components = [labor, material, machine, management];
  const hasComponent = components.some((v) => v !== null);
  let override = false;
  let finalTotal = total;
  let comment = "采用省定额价生成企业价草稿";
  if (hasComponent) {
    finalTotal = components.reduce((sum, value) => sum + (value || 0), 0);
    if (total !== null && Math.abs(total - finalTotal) > 0.01) {
      comment += `；省定额合计 ${total} 与人材机管合计 ${finalTotal.toFixed(2)} 存在差异，需人工确认`;
    }
  } else if (total !== null) {
    override = true;
    comment += "；省定额人材机管细项缺失，仅采用合计，需人工确认";
  }
  return {
    draft_labor_fee: labor,
    draft_material_fee: material,
    draft_machine_fee: machine,
    draft_management_fee: management,
    draft_total_fee: finalTotal,
    total_manual_override: override,
    cost_engineer_comment: comment,
  };
}

function fillProvincePrice(row) {
  applyDraftInputs(provinceValues(row));
  markDirty();
}

function scheduleAutosave() {
  window.clearTimeout(state.autosaveTimer);
  state.autosaveTimer = window.setTimeout(() => saveCurrentDraft("autosave_enterprise_draft", "autosaved", true), 2000);
}

function startAutosaveInterval() {
  window.clearInterval(state.autosaveInterval);
  state.autosaveInterval = window.setInterval(() => {
    if (hasUnsavedDraft()) saveCurrentDraft("autosave_enterprise_draft", "autosaved", true);
  }, 30000);
}

async function saveCurrentDraft(selectedSource = "manual_enterprise_draft", saveStatus = "saved", keepDialogOpen = false) {
  if (!state.currentDraftRow || !state.activeBill) return true;
  return saveDraft(state.currentDraftRow, selectedSource, { ...readDraftInputs(), save_status: saveStatus }, keepDialogOpen);
}

async function saveDraft(row, selectedSource, values, keepDialogOpen = false) {
  const payload = {
    bill_code_9: state.activeBill.bill_code_9,
    quota_source_code: row.quota_source_code,
    selected_price_source: selectedSource,
    draft_status: "draft",
    lock_status: "draft",
    local_cache_key: cacheKeyFor(state.activeBill.bill_code_9, row.quota_source_code),
    ...values,
  };
  try {
    setStatus(values.save_status === "autosaved" ? "自动保存中..." : "保存草稿中...");
    const result = await api("/api/draft/save", { method: "POST", body: JSON.stringify(payload) });
    clearDirty(keyFor(state.activeBill.bill_code_9, row.quota_source_code));
    state.pendingRetry = null;
    el.retrySaveBtn.classList.add("hidden");
    await selectBill(state.activeBill.bill_code_9, true);
    state.activeQuota = state.activeRows.find((r) => r.quota_source_code === row.quota_source_code) || null;
    renderRows();
    renderDetails();
    setStatus(values.save_status === "autosaved" ? "已自动保存" : "草稿已保存");
    if (!keepDialogOpen) el.dialog.close();
    if (result.draft) {
      el.dialogVersion.textContent = `版本 v${result.draft.draft_version}`;
      el.dialogLastSaved.textContent = `最后保存 ${empty(result.draft.last_saved_at || result.draft.updated_at)}`;
    }
    return true;
  } catch (error) {
    state.pendingRetry = { row, selectedSource, values, keepDialogOpen };
    localStorage.setItem(cacheKeyFor(state.activeBill.bill_code_9, row.quota_source_code), JSON.stringify(localCachePayload()));
    el.retrySaveBtn.classList.remove("hidden");
    setStatus(`保存失败：${error.message}`, "error");
    return false;
  }
}

async function useProvincePrice(quotaCode) {
  const row = findRow(quotaCode);
  if (!row || !state.activeBill) return;
  state.currentDraftRow = row;
  state.currentEditingKey = keyFor(state.activeBill.bill_code_9, row.quota_source_code);
  await saveDraft(row, "province_quota_price", { ...provinceValues(row), save_status: "saved" }, true);
}

async function clearDraft(quotaCode) {
  if (!state.activeBill) return;
  await guardNavigation(async () => {
    setStatus("清空草稿中...");
    await api("/api/draft/clear", { method: "POST", body: JSON.stringify({ bill_code_9: state.activeBill.bill_code_9, quota_source_code: quotaCode }) });
    clearDirty(keyFor(state.activeBill.bill_code_9, quotaCode));
    await selectBill(state.activeBill.bill_code_9, true);
    setStatus("草稿已清空");
  });
}

async function exportDrafts() {
  setStatus("导出草稿快照中...");
  const result = await api("/api/draft/export_snapshot");
  setStatus(`草稿快照已导出 ${result.count} 条`);
}

async function exportAudit() {
  setStatus("导出 audit 快照中...");
  const result = await api("/api/audit/export_snapshot");
  setStatus(`audit 快照已导出 ${result.count} 条`);
}

function initResize() {
  const left = localStorage.getItem("web_collab_leftPanelWidth") || "320px";
  const right = localStorage.getItem("web_collab_rightPanelWidth") || "370px";
  document.documentElement.style.setProperty("--left-width", left);
  document.documentElement.style.setProperty("--right-width", right);
  const bind = (splitter, side) => {
    splitter.addEventListener("mousedown", (event) => {
      event.preventDefault();
      splitter.classList.add("dragging");
      const startX = event.clientX;
      const startLeft = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--left-width"), 10) || 320;
      const startRight = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--right-width"), 10) || 370;
      const move = (moveEvent) => {
        const delta = moveEvent.clientX - startX;
        const width = el.workspace.getBoundingClientRect().width;
        if (side === "left") {
          const next = Math.max(240, Math.min(startLeft + delta, width - startRight - 600));
          document.documentElement.style.setProperty("--left-width", `${next}px`);
          localStorage.setItem("web_collab_leftPanelWidth", `${next}px`);
        } else {
          const next = Math.max(280, Math.min(startRight - delta, width - startLeft - 600));
          document.documentElement.style.setProperty("--right-width", `${next}px`);
          localStorage.setItem("web_collab_rightPanelWidth", `${next}px`);
        }
      };
      const up = () => {
        splitter.classList.remove("dragging");
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  };
  bind(el.leftSplitter, "left");
  bind(el.rightSplitter, "right");
}

async function init() {
  initResize();
  const data = await api("/api/tree/hierarchy");
  state.treeItems = data.items || [];
  state.treeNodes = buildTree(state.treeItems);
  const billCount = state.treeItems.filter((item) => item.node_type === "bill").length;
  el.treeCount.textContent = `${billCount} 个清单项`;
  renderTree();
  renderDetails();
  const firstBill = state.treeItems.find((item) => item.node_type === "bill");
  if (firstBill) await selectBill(firstBill.bill_code_9, true);
}

el.searchInput.addEventListener("input", renderTree);
el.closeDialogBtn.addEventListener("click", async () => {
  await guardNavigation(async () => el.dialog.close());
});
el.exportDraftBtn.addEventListener("click", exportDrafts);
el.exportAuditBtn.addEventListener("click", exportAudit);
el.retrySaveBtn.addEventListener("click", async () => {
  if (state.pendingRetry) await saveDraft(state.pendingRetry.row, state.pendingRetry.selectedSource, state.pendingRetry.values, state.pendingRetry.keepDialogOpen);
});
el.saveDraftBtn.addEventListener("click", () => saveCurrentDraft("manual_enterprise_draft", "saved", false));
el.useProvinceInDialogBtn.addEventListener("click", () => {
  if (state.currentDraftRow) fillProvincePrice(state.currentDraftRow);
});
[el.draftLabor, el.draftMaterial, el.draftMachine, el.draftManagement].forEach((input) => {
  input.addEventListener("input", () => {
    updateDraftTotal();
    markDirty();
  });
});
el.draftTotal.addEventListener("input", () => {
  el.manualOverride.checked = true;
  markDirty();
});
el.manualOverride.addEventListener("change", () => {
  updateDraftTotal();
  markDirty();
});
el.draftComment.addEventListener("input", markDirty);
window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedDraft()) return;
  event.preventDefault();
  event.returnValue = "存在未保存草稿";
});

init().catch((error) => {
  console.error(error);
  el.treeRoot.innerHTML = `<div class="empty-row">加载失败：${html(error.message)}</div>`;
});
