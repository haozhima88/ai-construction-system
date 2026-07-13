const state = {
  summary: null, bills: [], selectedBill: null, selectedRow: null,
  rows: [], evidence: null, activeTab: "province-pdf", pendingAction: null,
};

const el = Object.fromEntries([
  "summaryStatus", "draftStatus", "searchInput", "appendixFilter", "candidateFilter", "riskFilter", "draftFilter",
  "refreshBtn", "exportCurrent", "treeCount", "tree", "billTitle", "billMeta", "reviewSelect", "mappingRows",
  "detailType", "detail", "evidenceContent", "draftDialog", "dialogTitle", "dialogSource", "dialogQuota",
  "targetWrap", "targetBill", "draftReason", "confirmDraft",
].map(id => [id, document.getElementById(id)]));

function esc(value) {
  return String(value ?? "—").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

function badge(value) {
  const text = String(value || "pending");
  let cls = "pending";
  if (text.includes("high") || text.includes("exclude") || text.includes("mismatch")) cls = "high";
  else if (text.includes("low") || text.includes("direct") || text.includes("reviewed_candidate")) cls = "low";
  else if (text.includes("manual")) cls = "manual";
  return `<span class="badge ${cls}">${esc(text)}</span>`;
}

function dl(title, fields) {
  return `<section><h3>${esc(title)}</h3><dl>${fields.map(([name, value]) => `<dt>${esc(name)}</dt><dd>${esc(value)}</dd>`).join("")}</dl></section>`;
}

function groupBills(items) {
  const appendices = new Map();
  for (const bill of items) {
    if (!appendices.has(bill.appendix_code)) appendices.set(bill.appendix_code, {name: bill.appendix_name, sections: new Map()});
    const appendix = appendices.get(bill.appendix_code);
    if (!appendix.sections.has(bill.section_code)) appendix.sections.set(bill.section_code, {name: bill.section_name, bills: []});
    appendix.sections.get(bill.section_code).bills.push(bill);
  }
  return appendices;
}

function filteredBills() {
  const query = el.searchInput.value.trim().toLowerCase();
  return state.bills.filter(bill => {
    if (query && !`${bill.bill_code_9} ${bill.bill_name} ${bill.section_name}`.toLowerCase().includes(query)) return false;
    if (el.appendixFilter.value && bill.appendix_code !== el.appendixFilter.value) return false;
    if (el.candidateFilter.value === "yes" && Number(bill.original_count) === 0) return false;
    if (el.candidateFilter.value === "no" && Number(bill.original_count) !== 0) return false;
    if (el.riskFilter.value === "high" && bill.manual_review_required !== "yes") return false;
    if (el.riskFilter.value === "manual" && bill.manual_review_required !== "yes" && bill.review_state !== "needs_followup") return false;
    if (el.riskFilter.value === "evidence" && bill.authority_evidence_status !== "pending_evidence_link") return false;
    if (el.draftFilter.value === "copy" && !(Number(bill.copy_count) + Number(bill.copy_in_count))) return false;
    if (el.draftFilter.value === "move" && !(Number(bill.move_in_count) + Number(bill.move_out_count))) return false;
    if (el.draftFilter.value === "exclude" && !Number(bill.exclude_count)) return false;
    if (el.draftFilter.value === "reviewed" && bill.review_state === "not_reviewed") return false;
    return true;
  });
}

function renderTree() {
  const visible = filteredBills();
  el.treeCount.textContent = `${visible.length} / ${state.bills.length}`;
  const grouped = groupBills(visible);
  el.tree.innerHTML = [...grouped.entries()].map(([code, appendix]) => `
    <div class="tree-group" open>
      <button type="button"><span>▾</span><span class="tree-label">附录${esc(code)} ${esc(appendix.name)}</span><span class="counts">${[...appendix.sections.values()].reduce((n, s) => n + s.bills.length, 0)}</span></button>
      <div>${[...appendix.sections.entries()].map(([sectionCode, section]) => `
        <div class="tree-section">
          <button type="button"><span>▾</span><span class="tree-label">${esc(sectionCode)} ${esc(section.name)}</span><span class="counts">${section.bills.length}</span></button>
          <div>${section.bills.map(bill => {
            const changed = Number(bill.copy_count) + Number(bill.copy_in_count) + Number(bill.move_in_count) + Number(bill.move_out_count) + Number(bill.exclude_count);
            return `<button class="tree-item ${state.selectedBill?.bill_code_9 === bill.bill_code_9 ? "active" : ""}" data-bill="${esc(bill.bill_code_9)}" title="${esc(bill.bill_name)}"><span>·</span><span class="tree-label">${esc(bill.bill_code_9)} ${esc(bill.bill_name)}</span><span class="counts ${bill.manual_review_required === "yes" ? "warn" : ""}">${bill.original_count}/${bill.effective_count}${changed ? " Δ" : ""}</span></button>`;
          }).join("")}</div>
        </div>`).join("")}</div>
    </div>`).join("") || `<p class="empty">没有符合筛选条件的清单</p>`;
  el.tree.querySelectorAll(".tree-item").forEach(button => button.addEventListener("click", () => selectBill(button.dataset.bill)));
  el.tree.querySelectorAll(".tree-group > button, .tree-section > button").forEach(button => button.addEventListener("click", () => {
    const content = button.nextElementSibling; content.hidden = !content.hidden; button.firstElementChild.textContent = content.hidden ? "▸" : "▾";
  }));
}

async function loadAll() {
  const [summary, tree] = await Promise.all([api("/api/quota-building/summary"), api("/api/quota-building/tree")]);
  state.summary = summary; state.bills = tree.items;
  el.summaryStatus.textContent = `${summary.bill_count} 清单 · ${summary.quota_count} 定额 · ${summary.mapping_edge_count} 边`;
  el.draftStatus.textContent = `Draft ${summary.draft_count} · Audit ${summary.audit_count}`;
  const codes = [...new Set(state.bills.map(item => item.appendix_code))];
  const selected = el.appendixFilter.value;
  el.appendixFilter.innerHTML = `<option value="">全部</option>${codes.map(code => `<option value="${code}">附录${code}</option>`).join("")}`;
  el.appendixFilter.value = selected;
  renderTree();
}

async function selectBill(code) {
  const data = await api(`/api/quota-building/bill/${encodeURIComponent(code)}/rows`);
  state.selectedBill = state.bills.find(item => item.bill_code_9 === code) || data.bill;
  state.rows = data.rows; state.evidence = await api(`/api/quota-building/bill/${encodeURIComponent(code)}/evidence`);
  el.billTitle.textContent = `${data.bill.bill_code_9} ${data.bill.bill_name}`;
  el.billMeta.textContent = `附录${data.bill.appendix_code} · ${data.bill.section_code} ${data.bill.section_name} · ${data.bill.unit || "单位待核"}`;
  el.reviewSelect.disabled = false; el.reviewSelect.value = state.selectedBill.review_state || "not_reviewed";
  el.exportCurrent.classList.remove("disabled"); el.exportCurrent.href = `/api/quota-building/export/current/${code}`;
  renderTree(); renderRows(); renderBillDetail(data.bill);
  if (state.rows.length) await selectRow(state.rows[0]); else { state.selectedRow = null; renderEvidence(); }
}

function renderRows() {
  el.mappingRows.innerHTML = state.rows.map((item, index) => `
    <tr class="${item.effective ? "" : "ineffective"} ${state.selectedRow?.mapping_edge_id === item.mapping_edge_id && state.selectedRow?.row_origin === item.row_origin ? "selected" : ""}" data-index="${index}">
      <td>${index + 1}</td><td>${badge(item.row_origin)}</td><td>${esc(item.source_code)}</td><td>${esc(item.quota_name)}</td>
      <td>${esc(item.volume_code)}</td><td>${esc(item.quota_pdf_page_no)}</td><td>${esc(item.quota_unit)}</td>
      <td>${badge(item.routing_class)}</td><td>${esc(item.semantic_score)}</td><td>${badge(item.risk_level)}</td><td>${badge(item.review_status)}</td>
      <td><div class="row-actions">${item.draft_id ? `<button data-action="restore" title="恢复原关系">↶ 恢复</button>` : `<button data-action="copy" title="复制到其他清单">⧉</button><button data-action="move" title="移动到其他清单">⇥</button><button data-action="exclude" title="从当前清单排除">×</button>`}</div></td>
    </tr>`).join("") || `<tr><td colspan="12" class="empty">该清单没有自动候选，保留人工路由入口</td></tr>`;
  el.mappingRows.querySelectorAll("tr[data-index]").forEach(tr => {
    tr.addEventListener("click", event => { if (!event.target.closest("button")) selectRow(state.rows[Number(tr.dataset.index)]); });
    tr.querySelectorAll("button").forEach(button => button.addEventListener("click", event => { event.stopPropagation(); handleAction(button.dataset.action, state.rows[Number(tr.dataset.index)]); }));
  });
}

function renderBillDetail(bill) {
  const evidence = state.evidence?.evidence || {};
  el.detailType.textContent = "国标清单";
  el.detail.innerHTML = dl("国标清单", [["编码", bill.bill_code_9], ["名称", bill.bill_name], ["项目特征", bill.project_feature_raw], ["工作内容", bill.work_content_raw], ["工程量规则", bill.quantity_calculation_rule]]) +
    dl("来源治理", [["PDF 角色", "authority_source"], ["DOCX 角色", "extraction_proxy"], ["Baseline", "derived_reference_candidate"], ["证据状态", evidence.authority_verification_status || "pending_evidence_link"], ["冲突规则", "official_pdf_wins"]]);
}

async function selectRow(item) {
  state.selectedRow = item; renderRows();
  const detail = await api(`/api/quota-building/quota/${encodeURIComponent(item.quota_uid)}/detail`);
  item.quotaDetail = detail;
  el.detailType.textContent = "省定额";
  el.detail.innerHTML = dl("省定额", [["编码", item.source_code], ["名称", detail.quota.raw_name], ["册次", `${detail.quota.volume_code} ${detail.quota.volume_name}`], ["章节", `${detail.quota.chapter_code} / ${detail.quota.section_code}`], ["单位", detail.quota.unit_normalized], ["PDF 页", detail.quota.pdf_page_no], ["资源数", "切换工料机标签查看"]]) +
    dl("Mapping", [["角色", item.mapping_role], ["Routing", item.routing_class], ["风险", item.risk_level], ["草稿状态", item.draft_status || "无"], ["Review", item.review_status]]);
  renderEvidence();
}

async function renderEvidence() {
  const tab = state.activeTab, item = state.selectedRow;
  document.querySelectorAll(".tab").forEach(button => button.classList.toggle("active", button.dataset.tab === tab));
  if (tab === "authority") {
    const evidence = state.evidence?.evidence || {};
    const page = evidence.authority_pdf_page_no ? `#page=${evidence.authority_pdf_page_no}` : "";
    el.evidenceContent.innerHTML = `<div class="notice">官方 PDF：authority_source；DOCX：extraction_proxy；472 条 Baseline：derived_reference_candidate。${evidence.authority_verification_status === "pending_evidence_link" ? "官方 PDF 页证据待补，未伪造页码。" : "已登记官方证据。"}</div><iframe title="GB/T 50854 官方 PDF" src="/api/quota-building/pdf/authority${page}"></iframe>`;
    return;
  }
  if (tab === "v1v2") return renderApiTable(await api("/api/quota-building/v1-v2"));
  if (tab === "audit") return renderApiTable(await api("/api/quota-building/audit"));
  if (!item) { el.evidenceContent.innerHTML = `<p class="empty">选择省定额候选后显示来源证据</p>`; return; }
  if (tab === "province-pdf") {
    el.evidenceContent.innerHTML = `<iframe title="省定额 PDF 原页" src="/api/quota-building/pdf/province/${item.volume_code}#page=${item.quota_pdf_page_no || 1}"></iframe>`; return;
  }
  if (tab === "price") return renderApiTable({items: [item.quotaDetail?.price || {}]});
  if (tab === "mapping") {
    el.evidenceContent.innerHTML = `<div class="text-list"><div class="text-record"><strong>AI 候选解释</strong><br>${esc(item.ai_mapping_explanation)}</div><div class="text-record"><strong>风险说明</strong><br>${esc(item.risk_reason)}</div><div class="text-record"><strong>证据状态</strong><br>${esc(item.source_evidence_status)}</div></div>`; return;
  }
  const endpoints = {resources: "resources", work: "work-content", rules: "quantity-rules", conversions: "conversions", notes: "notes", issues: "issues"};
  const data = await api(`/api/quota-building/quota/${encodeURIComponent(item.quota_uid)}/${endpoints[tab]}`);
  if (tab === "issues") data.items = [...(data.items || []), ...(data.mapping_items || [])];
  renderApiTable(data);
}

function renderApiTable(data) {
  const items = data.items || [];
  if (!items.length) { el.evidenceContent.innerHTML = `<p class="empty">当前作用域没有记录</p>`; return; }
  const fields = Object.keys(items[0]).filter(key => key !== "scope").slice(0, 14);
  el.evidenceContent.innerHTML = `<table><thead><tr>${fields.map(field => `<th>${esc(field)}</th>`).join("")}</tr></thead><tbody>${items.map(item => `<tr>${fields.map(field => `<td>${esc(typeof item[field] === "object" ? JSON.stringify(item[field]) : item[field])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function handleAction(action, item) {
  if (action === "restore") return restore(item.draft_id);
  state.pendingAction = {action, item};
  el.dialogTitle.textContent = {copy: "复制候选关系", move: "移动候选关系", exclude: "排除当前候选"}[action];
  el.dialogSource.textContent = `${state.selectedBill.bill_code_9} ${state.selectedBill.bill_name}`;
  el.dialogQuota.textContent = `${item.source_code} ${item.quota_name}`;
  el.targetWrap.hidden = action === "exclude";
  el.targetBill.innerHTML = state.bills.filter(bill => bill.bill_code_9 !== state.selectedBill.bill_code_9).map(bill => `<option value="${bill.bill_code_9}">${bill.bill_code_9} ${esc(bill.bill_name)}</option>`).join("");
  el.draftReason.value = ""; el.draftDialog.showModal();
}

async function saveDraft(event) {
  event.preventDefault();
  const {action, item} = state.pendingAction;
  await api("/api/quota-building/draft/action", {method: "POST", body: JSON.stringify({source_edge_id: item.mapping_edge_id, target_bill_code_9: action === "exclude" ? "" : el.targetBill.value, action_type: action, operation_reason: el.draftReason.value})});
  el.draftDialog.close(); await loadAll(); await selectBill(state.selectedBill.bill_code_9);
}

async function restore(draftId) {
  await api(`/api/quota-building/draft/${draftId}/restore`, {method: "POST", body: "{}"});
  await loadAll(); await selectBill(state.selectedBill.bill_code_9);
}

async function saveReview() {
  if (!state.selectedBill) return;
  await api("/api/quota-building/review-state", {method: "POST", body: JSON.stringify({bill_code_9: state.selectedBill.bill_code_9, quota_uid: "", review_status: el.reviewSelect.value, comment: ""})});
  await loadAll();
}

for (const control of [el.searchInput, el.appendixFilter, el.candidateFilter, el.riskFilter, el.draftFilter]) control.addEventListener(control === el.searchInput ? "input" : "change", renderTree);
el.refreshBtn.addEventListener("click", loadAll);
el.reviewSelect.addEventListener("change", saveReview);
el.confirmDraft.addEventListener("click", saveDraft);
document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => { state.activeTab = button.dataset.tab; renderEvidence(); }));

loadAll().catch(error => { document.body.innerHTML = `<pre class="empty">${esc(error.message)}</pre>`; });
