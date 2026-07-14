const body = document.body;

class ReviewProvider {
  constructor(apiBase, readonly) { this.apiBase=apiBase;this.readonly=readonly; }
  async request(path, options={}) {
    const headers={"Accept":"application/json",...(options.headers||{})};
    if(options.body)headers["Content-Type"]="application/json";
    const response=await fetch(`${this.apiBase}${path}`,{...options,headers,credentials:"same-origin",cache:"no-store"});
    if(response.status===401&&!this.readonly){window.location.assign(`/login?next=${encodeURIComponent(location.pathname)}`);throw new Error("Authentication required");}
    if(!response.ok){const payload=await response.text();throw new Error(`${response.status} ${payload}`);}
    return response.json();
  }
  async identity() { return {roles:["read-only fallback"],permissions:[]}; }
  async mutate() { throw new Error("只读 Provider 不接受写入"); }
}

class PostgresReviewProvider extends ReviewProvider {
  constructor(apiBase) { super(apiBase,false); }
  async identity() {
    const response=await fetch("/api/v1/auth/me",{credentials:"same-origin",cache:"no-store"});
    if(response.status===401){window.location.assign(`/login?next=${encodeURIComponent(location.pathname)}`);throw new Error("Authentication required");}
    if(!response.ok)throw new Error(`Identity ${response.status}`);
    return response.json();
  }
  async mutate(path,method,payload,csrfToken) {
    return this.request(path,{method,headers:{"X-CSRF-Token":csrfToken||""},body:JSON.stringify(payload)});
  }
}

class SQLiteReadonlyReviewProvider extends ReviewProvider {
  constructor(apiBase) { super(apiBase,true); }
}

class QuotaReviewWorkbench {
  constructor(provider,state) { this.provider=provider;this.state=state; }
  async start() {
    loadPreferences();bindEvents();await loadIdentity();await loadWorkspace();
    if(this.state.bills.length)await selectBill(this.state.bills[0].bill_id);
  }
}

const provider=body.dataset.mode==="postgres"?new PostgresReviewProvider(body.dataset.apiBase):new SQLiteReadonlyReviewProvider(body.dataset.apiBase);
const API_BASE = provider.apiBase;
const READ_ONLY = provider.readonly;
const PREF_KEY = "quota_review_pg_preferences_v1";
const LAYOUT_KEYS = {
  mode:"review_layout_mode",density:"review_density",left:"left_pane_width",
  right:"right_pane_width",top:"top_pane_height",
};
const LAYOUT_MODES = new Set(["auto_fit","full_columns","compact_review"]);
const DENSITIES = new Set([80,90,100,110,125]);

const state = {
  me: null, summary: null, bills: [], allBills: [], selectedBill: null, selectedMapping: null,
  mappings: [], quota: null, resources: [], cost: null, work: [], rules: [],
  conversion: [], notes: [], evidence: null, authorityEvidence: null, activeTab: "resources", pendingAction: null,
  previewMode: "fit_region", zoomRatio: 1, provincePageOverride: null, detailCollapsed: false,
  layoutMode:"auto_fit",reviewDensity:100,
  textViewModes:{work:"structured",rules:"structured",conversion:"structured",notes:"structured"},
};

const el = Object.fromEntries([
  "backendBadge","summaryText","identityText","reviewWorkspace","treeCount","treeSearch",
  "priorityFilter","reviewFilter","treeRoot","billTitle","billMeta","reviewState",
  "mappingRows","tabButtons","tabMeta","tabContent","detailPane","detailMeta","billDetails",
  "quotaDetails","mappingDetails","sourceDetails","resetLayout","toggleDetail","leftSplitter",
  "rightSplitter","horizontalSplitter","draftDialog","draftDialogTitle","draftSource",
  "draftQuota","targetBillWrap","targetBill","operationReason","confirmDraft","layoutMode",
  "reviewDensity","candidateTableContainer",
].map(id => [id, document.getElementById(id)]));

function text(value) { return value === null || value === undefined || value === "" ? "—" : String(value); }
function html(value) { return text(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;"); }
function money(value) { const number = Number(value); return value === null || value === "" || Number.isNaN(number) ? "—" : number.toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2}); }
function status(value) { const key=String(value||"pending"); return `<span class="status ${html(key)}">${html(key)}</span>`; }
function priority(value) { return `<span class="priority ${html(value)}">${html(value)}</span>`; }
function can(permission) { return !READ_ONLY && Boolean(state.me?.permissions?.includes(permission)); }
function requestKey(prefix) { return `${prefix}-${crypto.randomUUID()}`; }

async function api(path, options={}) {
  return provider.request(path,options);
}

async function mutation(path, method, payload) {
  return provider.mutate(path,method,payload,state.me?.csrf_token);
}

function detailRows(rows) {
  return rows.map(([label,value])=>`<div class="detail-row"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join("");
}

function loadPreferences() {
  try {
    const prefs=JSON.parse(localStorage.getItem(PREF_KEY)||"{}");
    if (["resources","cost","work","rules","conversion","notes","provincePdf","authorityPdf","mapping","issues","v1v2","audit"].includes(prefs.selectedTab)) state.activeTab=prefs.selectedTab;
    if (["fit_region","fit_width","fit_height","actual_size","fullscreen"].includes(prefs.previewMode)) state.previewMode=prefs.previewMode;
    if (Number.isFinite(prefs.zoomRatio)) state.zoomRatio=Math.min(3,Math.max(.25,prefs.zoomRatio));
    const left=localStorage.getItem(LAYOUT_KEYS.left)||prefs.left;
    const right=localStorage.getItem(LAYOUT_KEYS.right)||prefs.right;
    const top=localStorage.getItem(LAYOUT_KEYS.top)||prefs.top;
    if (left) document.documentElement.style.setProperty("--left",left);
    if (right) document.documentElement.style.setProperty("--right",right);
    if (top) document.documentElement.style.setProperty("--top",top);
    state.detailCollapsed=Boolean(prefs.detailCollapsed);
    const storedMode=localStorage.getItem(LAYOUT_KEYS.mode)||prefs.layoutMode;
    const storedDensity=Number(localStorage.getItem(LAYOUT_KEYS.density)||prefs.reviewDensity||prefs.workspaceZoom);
    if(LAYOUT_MODES.has(storedMode))state.layoutMode=storedMode;
    if(DENSITIES.has(storedDensity))state.reviewDensity=storedDensity;
    if(prefs.textViewModes)state.textViewModes={...state.textViewModes,...prefs.textViewModes};
    el.reviewWorkspace.classList.toggle("detail-collapsed",state.detailCollapsed);
    applyReviewLayout();
  } catch (_) { localStorage.removeItem(PREF_KEY); }
}

function savePreferences() {
  const style=getComputedStyle(document.documentElement);
  localStorage.setItem(PREF_KEY,JSON.stringify({
    selectedTab:state.activeTab,previewMode:state.previewMode,zoomRatio:state.zoomRatio,
    left:style.getPropertyValue("--left").trim(),right:style.getPropertyValue("--right").trim(),
    top:style.getPropertyValue("--top").trim(),detailCollapsed:state.detailCollapsed,
    layoutMode:state.layoutMode,reviewDensity:state.reviewDensity,textViewModes:state.textViewModes,
  }));
  localStorage.setItem(LAYOUT_KEYS.mode,state.layoutMode);
  localStorage.setItem(LAYOUT_KEYS.density,String(state.reviewDensity));
  localStorage.setItem(LAYOUT_KEYS.left,style.getPropertyValue("--left").trim());
  localStorage.setItem(LAYOUT_KEYS.right,style.getPropertyValue("--right").trim());
  localStorage.setItem(LAYOUT_KEYS.top,style.getPropertyValue("--top").trim());
}

function applyReviewLayout() {
  el.reviewWorkspace.style.setProperty("--workspace-scale",String(state.reviewDensity/100));
  el.reviewDensity.value=String(state.reviewDensity);
  el.layoutMode.value=state.layoutMode;
  el.reviewWorkspace.dataset.reviewDensity=String(state.reviewDensity);
  el.reviewWorkspace.dataset.layoutMode=state.layoutMode;
  requestAnimationFrame(refreshResponsiveLayout);
}

function refreshResponsiveLayout() {
  const center=document.querySelector(".center-pane");
  if(center)el.reviewWorkspace.dataset.centerWidth=String(Math.round(center.getBoundingClientRect().width));
  if(el.candidateTableContainer)el.candidateTableContainer.dataset.availableWidth=String(Math.round(el.candidateTableContainer.clientWidth));
  computePreviewMetrics();
}

function cleanAppendixName(code,rawName) {
  const original=String(rawName||"").trim();
  const pattern=new RegExp(`^附录\\s*${String(code||"").replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}\\s*`,'i');
  return original.replace(pattern,"").trim()||original;
}

function groupedBills(items) {
  const groups=new Map();
  items.forEach(bill=>{
    if(!groups.has(bill.appendix_code))groups.set(bill.appendix_code,{name:bill.appendix_name,sections:new Map()});
    const appendix=groups.get(bill.appendix_code);
    if(!appendix.sections.has(bill.section_code))appendix.sections.set(bill.section_code,{name:bill.section_name,bills:[]});
    appendix.sections.get(bill.section_code).bills.push(bill);
  });
  return groups;
}

function filteredBills() {
  return state.bills.filter(bill=>{
    if(el.priorityFilter.value!=="all"&&bill.review_priority!==el.priorityFilter.value)return false;
    if(el.reviewFilter.value!=="all"&&bill.review_state!==el.reviewFilter.value)return false;
    return true;
  });
}

function renderTree() {
  const items=filteredBills(); el.treeCount.textContent=`${items.length} / ${state.summary?.bill_count||state.bills.length}`;
  const groups=groupedBills(items);
  el.treeRoot.innerHTML=[...groups.entries()].map(([appendixCode,appendix])=>`
    <div class="tree-group"><button type="button" title="${html(appendix.name)}"><span>▾</span><span class="tree-label">${html(cleanAppendixName(appendixCode,appendix.name))}</span><span>${[...appendix.sections.values()].reduce((n,s)=>n+s.bills.length,0)}</span></button>
      <div>${[...appendix.sections.entries()].map(([sectionCode,section])=>`
        <div class="tree-section"><button type="button"><span>▾</span><span class="tree-label">${html(sectionCode)} ${html(section.name)}</span><span>${section.bills.length}</span></button>
          <div>${section.bills.map(bill=>`<button type="button" class="tree-item ${state.selectedBill?.bill_id===bill.bill_id?"active":""}" data-bill="${html(bill.bill_id)}"><span>·</span><span class="tree-label">${html(bill.bill_code_9)} ${html(bill.bill_name)}</span><span class="tree-stats">${priority(bill.review_priority)}${bill.original_count?`<span class="tiny-count">${bill.original_count}</span>`:""}${bill.copy_in_count?`<span class="tiny-count">C${bill.copy_in_count}</span>`:""}${bill.move_in_count?`<span class="tiny-count">M${bill.move_in_count}</span>`:""}</span></button>`).join("")}</div>
        </div>`).join("")}</div>
    </div>`).join("")||`<div class="empty-state">没有符合条件的清单</div>`;
  el.treeRoot.querySelectorAll(".tree-item").forEach(button=>button.addEventListener("click",()=>selectBill(button.dataset.bill).catch(showFatal)));
  el.treeRoot.querySelectorAll(".tree-group>button,.tree-section>button").forEach(button=>button.addEventListener("click",()=>{const panel=button.nextElementSibling;panel.hidden=!panel.hidden;button.firstElementChild.textContent=panel.hidden?"▸":"▾";}));
}

async function loadIdentity() {
  if (READ_ONLY) {
    state.me=await provider.identity();
    el.identityText.textContent="development fallback";
    el.backendBadge.classList.add("fallback");
    return;
  }
  state.me=await provider.identity();
  el.identityText.textContent=`${state.me.user.display_name} · ${state.me.tenant.tenant_code}`;
}

async function loadWorkspace(query="") {
  const suffix=query?`?page_size=500&q=${encodeURIComponent(query)}`:"?page_size=500";
  const [summary,tree]=await Promise.all([api("/summary"),api(`/tree${suffix}`)]);
  state.summary=summary; state.bills=tree.items;
  if(!query)state.allBills=tree.items;
  el.summaryText.textContent=`${summary.bill_count} bill / ${summary.quota_count} quota / ${summary.resource_count||24981} resource / ${summary.mapping_edge_count} edge · Draft ${summary.draft_count} / Audit ${summary.audit_count}`;
  renderTree();
  if(READ_ONLY&&!document.querySelector(".readonly-note")){el.treeRoot.insertAdjacentHTML("beforebegin",`<div class="readonly-note">只读旧数据快照，不接受任何写入</div>`);}
}

async function selectBill(billId, preferredEdge=null) {
  const [billPayload,mappingPayload,authorityEvidence]=await Promise.all([
    api(`/bills/${encodeURIComponent(billId)}`),
    api(`/bills/${encodeURIComponent(billId)}/mappings`),
    api(`/bills/${encodeURIComponent(billId)}/authority-evidence`),
  ]);
  state.selectedBill=billPayload.bill; state.mappings=mappingPayload.items; state.selectedMapping=null;
  state.quota=null; state.resources=[]; state.cost=null; state.evidence=null;state.authorityEvidence=authorityEvidence;state.provincePageOverride=null;
  el.billTitle.textContent=`${state.selectedBill.bill_code_9} ${state.selectedBill.bill_name}`;
  el.billMeta.textContent=`附录${state.selectedBill.appendix_code} · ${state.selectedBill.section_code} ${state.selectedBill.section_name} · ${state.selectedBill.unit||"单位待核"}`;
  renderTree(); renderMappings(); renderBillDetails();
  const preferred=state.mappings.find(row=>row.edge_id===preferredEdge)||state.mappings[0];
  if(preferred)await selectMapping(preferred);else renderEmptySelection("当前清单无省定额候选");
}

class MappingActionCell {
  constructor(row) { this.row=row; }

  definitions() {
    const original=this.row.row_origin==="original_candidate";
    const copied=this.row.row_origin==="draft_copy"&&this.row.draft_state==="active";
    const restorable=Boolean(this.row.draft_id)&&this.row.draft_state==="active";
    if(copied)return [
      ["move","Move","移动该 Draft 候选到其他清单","mapping_draft.update"],
      ["exclude","Exclude","从 Overlay 排除该 Draft 候选","mapping_draft.exclude"],
      ["restore","Restore","恢复复制前的候选状态","mapping_draft.update"],
    ];
    if(restorable)return [["restore","Restore","恢复原始候选状态","mapping_draft.update"]];
    if(original)return [
      ["copy","Copy","复制到其他清单","mapping_draft.create"],
      ["move","Move","移动到其他清单","mapping_draft.update"],
      ["exclude","Exclude","从 Overlay 排除","mapping_draft.exclude"],
    ];
    return [];
  }

  readonly(reason) {
    return `<span class="action-readonly" title="${html(reason)}" data-disabled-reason="${html(reason)}">只读</span>`;
  }

  render() {
    if(READ_ONLY)return this.readonly("SQLite 只读回退不接受 Draft 写入");
    const definitions=this.definitions();
    if(!definitions.length)return this.readonly("当前记录没有可用的 Draft 操作");
    const permitted=definitions.filter(([, , ,permission])=>can(permission));
    if(!permitted.length)return this.readonly("当前角色未分配 Mapping Draft 编辑权限");
    return permitted.map(([action,label,tooltip,permission])=>
      `<button type="button" data-action="${action}" data-required-permission="${permission}" aria-label="${html(tooltip)}" title="${html(tooltip)}">${label}</button>`
    ).join("");
  }
}

function actionsFor(row) {
  return new MappingActionCell(row).render();
}

function renderMappings() {
  el.mappingRows.innerHTML=state.mappings.map((row,index)=>`<tr data-row="${index}" class="${row.effective?"":"hidden-edge"} ${state.selectedMapping?.edge_id===row.edge_id&&state.selectedMapping?.row_origin===row.row_origin?"selected":""}">
    <td class="cell-index">${index+1}</td><td class="cell-origin">${status(row.row_origin)}</td><td>${html(row.source_code)}</td><td class="candidate-name">${html(row.quota_name)}<span class="secondary">${html(row.mapping_role)} · ${html(row.routing_class)}</span></td><td>${html(row.quota_unit)}</td><td class="cost-cell">${money(row.labor_fee)}</td><td class="cost-cell">${money(row.material_fee)}</td><td class="cost-cell">${money(row.machine_fee)}</td><td class="cost-cell">${money(row.management_fee)}</td><td class="cost-cell">${money(row.total_fee)}</td><td>${status(row.review_status)} ${priority(row.review_priority)}</td><td class="action-column"><div class="row-actions">${actionsFor(row)}</div></td>
  </tr>`).join("")||`<tr><td colspan="12" class="empty-state">当前清单无省定额候选</td></tr>`;
  el.mappingRows.querySelectorAll("tr[data-row]").forEach(tr=>{
    const row=state.mappings[Number(tr.dataset.row)];
    tr.addEventListener("click",event=>{if(!event.target.closest("button"))selectMapping(row).catch(showFatal);});
    tr.querySelectorAll("button[data-action]").forEach(button=>button.addEventListener("click",event=>{event.stopPropagation();openDraft(button.dataset.action,row);}));
  });
}

async function selectMapping(row) {
  state.selectedMapping=row; renderMappings();
  el.reviewState.value=row.review_status||"not_reviewed";
  el.reviewState.disabled=!can("mapping_review.update");
  const quotaId=encodeURIComponent(row.quota_id||row.quota_uid);
  const [quota,resources,cost,work,rulesPayload,conversion,notes,evidence]=await Promise.all([
    api(`/quotas/${quotaId}`),api(`/quotas/${quotaId}/resources?page_size=500`),
    api(`/quotas/${quotaId}/cost-summary`),api(`/quotas/${quotaId}/work-content`),
    api(`/quotas/${quotaId}/quantity-rules`),api(`/quotas/${quotaId}/conversion-rules`),
    api(`/quotas/${quotaId}/notes`),api(`/quotas/${quotaId}/evidence`),
  ]);
  state.quota=quota.quota;state.resources=resources.items;state.cost=cost;state.work=work.items;
  state.rules=rulesPayload.items;state.conversion=conversion.items;state.notes=notes.items;state.evidence=evidence;
  el.tabMeta.textContent=`${row.source_code} ${row.quota_name}`;
  renderQuotaDetails(); renderMappingDetails(); renderActiveTab();
}

function renderBillDetails() {
  const bill=state.selectedBill||{};
  el.billDetails.innerHTML=detailRows([["编码",bill.bill_code_9],["名称",bill.bill_name],["单位",bill.unit],["项目特征",bill.project_feature_raw],["工作内容",bill.work_content_raw],["工程量规则",bill.quantity_calculation_rule],["来源路径",bill.source_heading_path]]);
}

function renderQuotaDetails() {
  const quota=state.quota||{};
  el.detailMeta.textContent=`${quota.volume_code||"—"} / PDF ${quota.pdf_page_no||"—"}`;
  el.quotaDetails.innerHTML=detailRows([["编码",quota.source_code],["名称",quota.quota_name],["规格",quota.specification],["单位",quota.unit],["册次",quota.volume_code],["章节",`${text(quota.chapter_code)} / ${text(quota.section_code)}`],["PDF页",quota.pdf_page_no],["省定额基价",money(quota.total_fee)]]);
  const doc=quota.source_document||{};
  el.sourceDetails.innerHTML=detailRows([["文档",doc.document_name],["来源角色",doc.source_role],["权威状态",doc.authority_status],["可读状态",doc.readable_status],["SHA256",doc.sha256]]);
}

function renderMappingDetails() {
  const row=state.selectedMapping||{};
  el.mappingDetails.innerHTML=detailRows([["角色",row.mapping_role],["Routing",row.routing_class],["风险",`${text(row.review_priority)} · ${text(row.risk_level)}`],["风险原因",row.risk_reason],["解释",row.ai_mapping_explanation],["Review",row.review_status],["Draft",`${text(row.draft_action)} / ${text(row.draft_status)}`],["Edge ID",row.edge_id]]);
}

function renderEmptySelection(message) {
  el.mappingRows.innerHTML=`<tr><td colspan="12" class="empty-state">${html(message)}</td></tr>`;
  el.tabContent.innerHTML=`<div class="empty-state">${html(message)}</div>`;
}

function table(items,columns) {
  if(!items.length)return `<div class="empty-state">没有记录</div>`;
  return `<table class="data-table"><thead><tr>${columns.map(([,label])=>`<th>${html(label)}</th>`).join("")}</tr></thead><tbody>${items.map(item=>`<tr>${columns.map(([key])=>`<td>${html(item[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function renderResources() {
  const columns=[["resource_code","资源编码"],["resource_name","名称"],["resource_category","类别"],["unit","单位"],["consumption","消耗量"],["unit_price","省定额单价"],["source_component_amount","原始合价"],["calculated_component_amount","计算合价"],["display_component_amount_2dp","显示合价"],["amount_source","金额来源"]];
  const rows=state.resources.map(row=>({...row,amount_source:status(row.amount_source)}));
  const bodyHtml=rows.length?`<table class="data-table"><thead><tr>${columns.map(([,label])=>`<th>${label}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr>${columns.map(([key])=>`<td class="${key==="amount_source"?"amount-source":""}">${key==="amount_source"?row[key]:html(row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`:`<div class="empty-state">无工料机记录</div>`;
  const c=state.cost||{};
  el.tabContent.innerHTML=bodyHtml+`<div class="summary-band"><div class="summary-cell">人工合计<strong>${money(c.labor_calculated_total)}</strong></div><div class="summary-cell">材料合计<strong>${money(c.material_calculated_total)}</strong></div><div class="summary-cell">机具合计<strong>${money(c.machine_calculated_total)}</strong></div><div class="summary-cell">其他合计<strong>${money(c.other_calculated_total)}</strong></div><div class="summary-cell">资源合计<strong>${money(c.resource_calculated_total)}</strong></div></div><div class="reconciliation ${c.reconciliation_status==="matched"?"":"alert"}">${status(c.reconciliation_status)} · 管理费 ${money(c.management_fee)} · 省定额基价 ${money(c.provincial_base_price)} · 差额 ${money(c.reconciliation_delta)} · ${html(c.reconciliation_reason)}</div>`;
}

function renderCost() {
  const c=state.cost||{};
  const rows=[
    ["人工合计",c.labor_source_total,c.labor_calculated_total],["材料合计",c.material_source_total,c.material_calculated_total],
    ["机具合计",c.machine_source_total,c.machine_calculated_total],["其他合计",c.other_source_total,c.other_calculated_total],
    ["资源合计",c.resource_source_total,c.resource_calculated_total],
  ].map(([name,source,calculated])=>({name,source:money(source),calculated:money(calculated)}));
  el.tabContent.innerHTML=table(rows,[["name","分类"],["source","原始合计"],["calculated","显示/回退合计"]])+`<div class="reconciliation ${c.reconciliation_status==="matched"?"":"alert"}"><strong>${status(c.reconciliation_status)}</strong><br>资源 ${money(c.resource_calculated_total)} + 管理费 ${money(c.management_fee)} − 省定额基价 ${money(c.provincial_base_price)} = ${money(c.reconciliation_delta)}<br>${html(c.reconciliation_reason)}</div>`;
}

function markerLevel(marker,fallback="原记录") {
  if(/^[一二三四五六七八九十]+、$/.test(marker))return "章/节";
  if(/^[（(]/.test(marker))return "子项";
  if(/^\d+[.、]$/.test(marker)||/^[①-⑳]$/.test(marker))return "条款";
  if(/^注/.test(marker))return "注";
  if(/^表/.test(marker))return "表";
  return fallback;
}

function hierarchyLabel(row) {
  const marker=String(row?.rule_code||row?.rule_title||"");
  return markerLevel(marker,row?.rule_title?"章/节":"原记录");
}

function splitMarkedText(value,fallbackNo="",fallbackLevel="原记录") {
  const source=String(value||"").replace(/\s+/g," ").trim();
  if(!source)return [];
  const markerPattern=/(^|[\s。；;：:])((?:[一二三四五六七八九十]+、)|(?:[（(][一二三四五六七八九十0-9]+[）)])|(?:\d{1,2}[.、](?=\s*[\u4e00-\u9fffA-Za-z]))|(?:[①-⑳])|(?:注(?:释)?[:：]?)|(?:表(?:[一二三四五六七八九十]|\d+|-\d+)?(?=\s)))/gu;
  const matches=[...source.matchAll(markerPattern)].map(match=>({index:match.index+match[1].length,marker:match[2]}));
  if(!matches.length)return [{level:fallbackLevel,number:fallbackNo||"—",content:source,split_status:"split_uncertain"}];
  const result=[];
  const prefix=source.slice(0,matches[0].index).trim().replace(/^\d+\s+(?:说\s*明|工程量计算规则)\s*/,"").trim();
  if(prefix)result.push({level:fallbackLevel,number:fallbackNo||"总则",content:prefix,split_status:"structured"});
  matches.forEach((match,index)=>{
    const next=matches[index+1]?.index??source.length;
    const content=source.slice(match.index+match.marker.length,next).trim();
    if(content)result.push({level:markerLevel(match.marker),number:match.marker,content,split_status:"structured"});
  });
  return result.length?result:[{level:fallbackLevel,number:fallbackNo||"—",content:source,split_status:"split_uncertain"}];
}

function structuredRows(kind,items) {
  let sequence=0;
  return items.flatMap((row,rowIndex)=>{
    const fallback=kind==="rules"?(row.rule_code||row.rule_title||String(rowIndex+1)):String(rowIndex+1);
    return splitMarkedText(row.rule_text,fallback,kind==="rules"?hierarchyLabel(row):"原记录").map(part=>({
      seq_no:++sequence,hierarchy_level:part.level,rule_no:part.number,
      rule_title:row.rule_title||"—",content:part.content,rule_text:part.content,
      pdf_page:row.pdf_page_no||"—",scope_type:row.scope_type||"—",
      scope_status:row.scope_status||part.split_status,split_status:part.split_status,
    }));
  });
}

function pdfPageButton(page) {
  return /^\d+$/.test(String(page||""))?`<button class="pdf-page-link" type="button" data-pdf-page="${html(page)}" title="查看省定额 PDF 原页">P${html(page)} ↗</button>`:"—";
}

function structuredTable(kind,rows) {
  const columns=kind==="work"
    ?[["seq_no","序号","col-number"],["content","内容",""] ,["pdf_page","PDF页","col-page"],["scope_status","作用域状态","col-status"]]
    :kind==="rules"
      ?[["hierarchy_level","层级","col-level"],["rule_no","规则号","col-number"],["rule_title","规则标题","col-title"],["rule_text","规则内容",""] ,["pdf_page","PDF页","col-page"],["scope_type","作用域","col-level"],["scope_status","作用域状态","col-status"]]
      :[["rule_no",kind==="notes"?"注释序号":"规则号","col-number"],["content","内容",""] ,["pdf_page","PDF页","col-page"],["scope_status","作用域状态","col-status"]];
  return `<table class="data-table structured-table"><colgroup>${columns.map(([, ,className])=>`<col class="${className}">`).join("")}</colgroup><thead><tr>${columns.map(([,label])=>`<th>${html(label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr data-split-status="${html(row.split_status)}">${columns.map(([key])=>`<td>${key==="pdf_page"?pdfPageButton(row[key]):html(row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function rawTextView(items,title) {
  return `<div class="raw-view">${items.map((row,index)=>`<article class="raw-record"><div class="raw-record-head"><strong>${html(title)}原文 ${index+1}</strong>${pdfPageButton(row.pdf_page_no)}</div><div class="raw-record-text">${html(row.rule_text)}</div><div class="secondary">${html(row.scope_type)} · ${html(row.scope_status||row.source_locator)}</div></article>`).join("")}</div>`;
}

function bindTextViewActions(kind) {
  el.tabContent.querySelectorAll("button[data-text-mode]").forEach(button=>button.addEventListener("click",()=>{state.textViewModes[kind]=button.dataset.textMode;savePreferences();renderActiveTab();}));
  el.tabContent.querySelectorAll("button[data-pdf-page]").forEach(button=>button.addEventListener("click",()=>{state.provincePageOverride=Number(button.dataset.pdfPage);state.activeTab="provincePdf";savePreferences();renderActiveTab();}));
}

function renderStructuredTextTab(kind,items,title,emptyMessage) {
  if(!items.length){el.tabContent.innerHTML=`<div class="empty-state">${html(emptyMessage)}</div>`;return;}
  const rows=structuredRows(kind,items),mode=state.textViewModes[kind]||"structured";
  const rawLabel=kind==="rules"?"原文 PDF 视图":"原文视图";
  el.tabContent.innerHTML=`<div class="text-view"><div class="text-view-toolbar"><div class="segmented-control" role="group" aria-label="${html(title)}视图"><button type="button" data-text-mode="structured" class="${mode==="structured"?"active":""}">结构化视图</button><button type="button" data-text-mode="raw" class="${mode==="raw"?"active":""}">${rawLabel}</button></div><span class="text-view-meta">${mode==="structured"?`${rows.length} 条结构记录`:`${items.length} 条原始记录`}</span></div>${mode==="structured"?structuredTable(kind,rows):rawTextView(items,title)}</div>`;
  bindTextViewActions(kind);
}

function previewUrl(kind) {
  if(!state.selectedMapping)return "";
  const quotaId=encodeURIComponent(state.selectedMapping.quota_id||state.selectedMapping.quota_uid);
  const base=kind==="authorityPdf"?`${API_BASE}/authority/pdf`:`${API_BASE}/quotas/${quotaId}/pdf`;
  const page=kind==="authorityPdf"?state.authorityEvidence?.official_pdf_page_no:(state.provincePageOverride||state.quota?.pdf_page_no);
  const zoom={fit_region:"page-fit",fit_width:"page-width",fit_height:"page-height",actual_size:String(Math.round(state.zoomRatio*100)),fullscreen:"page-fit"}[state.previewMode];
  return page?`${base}#page=${page}&zoom=${zoom}`:`${base}#zoom=${zoom}`;
}

function setPreviewState(name,message) {
  const panel=document.getElementById("previewState");if(!panel)return;
  panel.dataset.state=name;panel.textContent=message;panel.classList.toggle("visible",name!=="ready");
}

function renderPreview(kind) {
  const isAuthority=kind==="authorityPdf";
  const hasSource=isAuthority?Boolean(state.authorityEvidence?.authority_document?.source_available):Boolean(state.evidence?.document?.source_available);
  const hasPage=isAuthority?Boolean(state.authorityEvidence?.official_pdf_page_no):Boolean(state.provincePageOverride||state.quota?.pdf_page_no);
  const evidenceMeta=isAuthority?`<span class="evidence-governance">authority source · official PDF · extraction proxy DOCX · ${html(state.authorityEvidence?.authority_verification_status||"pending_evidence_link")}</span>`:"";
  const openUnlocated=isAuthority&&!hasPage?`<button id="openUnlocatedAuthority" class="open-pdf-command" type="button">打开官方 PDF（未定位）</button>`:"";
  el.tabContent.innerHTML=`<div id="previewShell" class="preview-shell"><div id="previewToolbar" class="preview-toolbar">${evidenceMeta}<select id="previewMode" aria-label="预览模式"><option value="fit_region">适合区域</option><option value="fit_width">适合宽度</option><option value="fit_height">适合高度</option><option value="actual_size">实际大小</option><option value="fullscreen">全屏</option></select><button id="zoomOut" title="缩小">−</button><button id="zoomReset" title="100%">100%</button><button id="zoomIn" title="放大">＋</button><button id="previewDefault" title="恢复默认">↺</button>${openUnlocated}<span id="previewMetrics" class="preview-metrics">计算可用区域</span></div><div id="previewRegion" class="preview-region"><iframe id="previewFrame" title="PDF 原页预览"></iframe><div id="previewState" class="preview-state visible" data-state="loading">正在加载 PDF</div></div></div>`;
  const mode=document.getElementById("previewMode");mode.value=state.previewMode;
  mode.addEventListener("change",()=>{state.previewMode=mode.value;savePreferences();if(state.previewMode==="fullscreen")document.getElementById("previewShell").requestFullscreen().catch(()=>{});updatePreviewFrame(kind);});
  document.getElementById("zoomOut").addEventListener("click",()=>{state.zoomRatio=Math.max(.25,state.zoomRatio-.1);state.previewMode="actual_size";mode.value=state.previewMode;savePreferences();updatePreviewFrame(kind);});
  document.getElementById("zoomIn").addEventListener("click",()=>{state.zoomRatio=Math.min(3,state.zoomRatio+.1);state.previewMode="actual_size";mode.value=state.previewMode;savePreferences();updatePreviewFrame(kind);});
  document.getElementById("zoomReset").addEventListener("click",()=>{state.zoomRatio=1;state.previewMode="actual_size";mode.value=state.previewMode;savePreferences();updatePreviewFrame(kind);});
  document.getElementById("previewDefault").addEventListener("click",()=>{state.zoomRatio=1;state.previewMode="fit_region";mode.value=state.previewMode;savePreferences();updatePreviewFrame(kind);});
  const frame=document.getElementById("previewFrame");
  frame.addEventListener("load",()=>setPreviewState("ready",""));
  frame.addEventListener("error",()=>setPreviewState("failed","PDF 加载失败"));
  if(!hasSource){setPreviewState("source_missing","PDF 来源文件不可用");return;}
  if(!hasPage){
    setPreviewState("pending_evidence_link",isAuthority?"官方 PDF 页证据待补":"当前记录没有可用页码");
    document.getElementById("openUnlocatedAuthority")?.addEventListener("click",()=>updatePreviewFrame(kind));
    observePreview();return;
  }
  updatePreviewFrame(kind);
  observePreview();
}

let previewRequestId=0;
async function updatePreviewFrame(kind) {
  const frame=document.getElementById("previewFrame");if(!frame)return;
  const url=previewUrl(kind);const requestId=++previewRequestId;
  setPreviewState("loading","正在加载 PDF");computePreviewMetrics();
  try {
    const response=await fetch(url.split("#")[0],{headers:{Range:"bytes=0-1023"},credentials:"same-origin"});
    const contentType=response.headers.get("content-type")||"";
    if(!response.ok||!contentType.startsWith("application/pdf"))throw new Error(`PDF ${response.status}`);
    if(requestId!==previewRequestId||!document.body.contains(frame))return;
    frame.src=url;setPreviewState("ready","");
  } catch(error) {
    if(requestId===previewRequestId)setPreviewState("failed",`PDF 加载失败 · ${error.message}`);
  }
}

function computePreviewMetrics() {
  const shell=document.getElementById("previewShell"),toolbar=document.getElementById("previewToolbar"),region=document.getElementById("previewRegion"),metrics=document.getElementById("previewMetrics");
  if(!shell||!toolbar||!region||!metrics)return;
  const rect=shell.getBoundingClientRect();const toolbarHeight=toolbar.getBoundingClientRect().height;
  const tabHeight=document.querySelector(".tabs-bar")?.getBoundingClientRect().height||0;
  metrics.textContent=`${Math.round(region.clientWidth)} × ${Math.round(region.clientHeight)} · 工具栏 ${Math.round(toolbarHeight)} · Tabs ${Math.round(tabHeight)}`;
  region.dataset.availableWidth=String(Math.round(rect.width));region.dataset.availableHeight=String(Math.max(0,Math.round(rect.height-toolbarHeight)));
}

let previewObserver=null;
function observePreview() {
  previewObserver?.disconnect();previewObserver=new ResizeObserver(computePreviewMetrics);
  [el.reviewWorkspace,document.querySelector(".center-pane"),document.querySelector(".evidence-panel"),document.getElementById("previewShell"),document.getElementById("previewRegion"),el.leftSplitter,el.rightSplitter,el.horizontalSplitter].filter(Boolean).forEach(node=>previewObserver.observe(node));
}

async function renderAudit() {
  try { const payload=await api("/audit?page_size=200");el.tabContent.innerHTML=table(payload.items,[["event_at","时间"],["event_type","事件"],["source_audit_key","幂等键"],["actor_user_id","操作者"],["draft_id","Draft"]]); }
  catch(error){el.tabContent.innerHTML=`<div class="fatal-state">${html(error.message)}</div>`;}
}

function renderMappingExplanation() {
  const row=state.selectedMapping||{};
  el.tabContent.innerHTML=`<div class="explanation-grid"><section><h3>Mapping 解释</h3><p>${html(row.ai_mapping_explanation||"当前候选无额外解释")}</p></section><section><h3>路由与风险</h3><p>${html(row.mapping_role)} · ${html(row.routing_class)} · ${html(row.review_priority)} / ${html(row.risk_level)}</p><p>${html(row.risk_reason||row.priority_reason||"未登记风险原因")}</p></section><section><h3>算法与证据</h3><dl>${detailRows([["semantic",row.semantic_score],["候选排序",row.candidate_rank],["证据状态",row.source_evidence_status],["Edge ID",row.edge_id]])}</dl></section></div>`;
}

function renderIssues() {
  const row=state.selectedMapping||{};
  const issues=[];
  if(row.risk_reason)issues.push(["Mapping 风险",row.risk_reason]);
  if(row.routing_class==="manual_review_required")issues.push(["人工审核",row.priority_reason||"该候选需要人工审核"]);
  if(state.cost?.reconciliation_status&&state.cost.reconciliation_status!=="matched")issues.push(["费用对账",`${state.cost.reconciliation_status} · ${state.cost.reconciliation_reason||""}`]);
  if(!state.authorityEvidence?.official_pdf_page_no)issues.push(["国标证据","官方 PDF 页证据待补"]);
  el.tabContent.innerHTML=issues.length?`<div class="issue-list">${issues.map(([title,content])=>`<article><strong>${html(title)}</strong><p>${html(content)}</p></article>`).join("")}</div>`:`<div class="empty-state">当前候选无已登记 Issues</div>`;
}

function renderV1V2() {
  el.tabContent.innerHTML=`<div class="empty-state"><strong>当前 PostgreSQL RC1 未登记 V1/V2 差异记录</strong><br>该标签保持只读可见，不将缺失数据伪装为已核验。</div>`;
}

function renderActiveTab() {
  el.tabButtons.querySelectorAll("button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.activeTab));
  if(!state.selectedMapping){el.tabContent.innerHTML=`<div class="empty-state">请选择定额候选</div>`;return;}
  if(state.activeTab==="resources")renderResources();
  else if(state.activeTab==="cost")renderCost();
  else if(state.activeTab==="work")renderStructuredTextTab("work",state.work,"工作内容","当前定额无工作内容记录");
  else if(state.activeTab==="rules")renderStructuredTextTab("rules",state.rules,"工程量规则","当前定额无直接适用的工程量规则");
  else if(state.activeTab==="conversion")renderStructuredTextTab("conversion",state.conversion,"换算规则","当前定额无直接适用的换算规则");
  else if(state.activeTab==="notes")renderStructuredTextTab("notes",state.notes,"注释","当前定额无直接适用的注释");
  else if(state.activeTab==="provincePdf"||state.activeTab==="authorityPdf")renderPreview(state.activeTab);
  else if(state.activeTab==="mapping")renderMappingExplanation();
  else if(state.activeTab==="issues")renderIssues();
  else if(state.activeTab==="v1v2")renderV1V2();
  else if(state.activeTab==="audit")renderAudit();
}

function openDraft(action,row) {
  if(READ_ONLY)return;
  if(action==="restore"){restoreDraft(row).catch(showFatal);return;}
  state.pendingAction={action,row};
  el.draftDialogTitle.textContent=`${action[0].toUpperCase()+action.slice(1)} Mapping Draft`;
  el.draftSource.textContent=`${state.selectedBill.bill_code_9} ${state.selectedBill.bill_name}`;
  el.draftQuota.textContent=`${row.source_code} ${row.quota_name}`;
  el.targetBillWrap.hidden=action==="exclude";
  el.targetBill.innerHTML=state.allBills.filter(b=>b.bill_id!==state.selectedBill.bill_id).map(b=>`<option value="${html(b.bill_code_9)}">${html(b.bill_code_9)} ${html(b.bill_name)}</option>`).join("");
  el.operationReason.value="";el.draftDialog.showModal();
}

async function confirmDraft(event) {
  event.preventDefault();const pending=state.pendingAction;if(!pending)return;
  const payload={edge_id:pending.row.edge_id,target_bill_code_9:pending.action==="exclude"?null:el.targetBill.value,operation_reason:el.operationReason.value,row_version:pending.row.row_version,idempotency_key:requestKey(`draft-${pending.action}`)};
  await mutation(`/mapping-drafts/${pending.action}`,"POST",payload);el.draftDialog.close();
  await refreshSelectedBill();
}

async function restoreDraft(row) {
  await mutation("/mapping-drafts/restore","POST",{draft_id:row.draft_id,row_version:row.draft_row_version,idempotency_key:requestKey("draft-restore")});
  await refreshSelectedBill();
}

async function saveReview() {
  const row=state.selectedMapping;if(!row||!can("mapping_review.update"))return;
  await mutation(`/mappings/${encodeURIComponent(row.edge_id)}/review-state`,"PATCH",{review_status:el.reviewState.value,comment:"",row_version:row.review_row_version,idempotency_key:requestKey("review")});
  await refreshSelectedBill(row.edge_id);
}

async function refreshSelectedBill(preferredEdge=null) {
  const billId=state.selectedBill.bill_id;
  const targetEdge=preferredEdge||state.selectedMapping?.edge_id||null;
  await loadWorkspace(el.treeSearch.value.trim());
  await selectBill(billId,targetEdge);
}

function setupSplitter(splitter,type) {
  splitter.addEventListener("pointerdown",event=>{
    event.preventDefault();splitter.setPointerCapture(event.pointerId);splitter.classList.add("dragging");
    const move=moveEvent=>{
      const rect=el.reviewWorkspace.getBoundingClientRect();
      if(type==="left")document.documentElement.style.setProperty("--left",`${Math.max(220,Math.min(480,moveEvent.clientX-rect.left))}px`);
      if(type==="right")document.documentElement.style.setProperty("--right",`${Math.max(280,Math.min(520,rect.right-moveEvent.clientX))}px`);
      if(type==="top")document.documentElement.style.setProperty("--top",`${Math.max(240,Math.min(rect.height-220,moveEvent.clientY-rect.top))}px`);
      refreshResponsiveLayout();
    };
    const up=()=>{splitter.classList.remove("dragging");splitter.removeEventListener("pointermove",move);splitter.removeEventListener("pointerup",up);savePreferences();};
    splitter.addEventListener("pointermove",move);splitter.addEventListener("pointerup",up);
  });
}

function defaultPaneLayout() {
  return window.innerWidth<=1500?{left:"230px",right:"280px",top:"54%"}:{left:"300px",right:"340px",top:"54%"};
}

function resetLayout() {
  const defaults=defaultPaneLayout();
  document.documentElement.style.setProperty("--left",defaults.left);document.documentElement.style.setProperty("--right",defaults.right);document.documentElement.style.setProperty("--top",defaults.top);
  state.previewMode="fit_region";state.zoomRatio=1;state.layoutMode="auto_fit";state.reviewDensity=100;state.detailCollapsed=false;el.reviewWorkspace.classList.remove("detail-collapsed");applyReviewLayout();savePreferences();refreshResponsiveLayout();
}

function showFatal(error) { console.error(error);el.tabContent.innerHTML=`<div class="fatal-state">${html(error.message||error)}</div>`; }

function bindEvents() {
  let searchTimer=null;el.treeSearch.addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadWorkspace(el.treeSearch.value.trim()).catch(showFatal),250);});
  el.priorityFilter.addEventListener("change",renderTree);el.reviewFilter.addEventListener("change",renderTree);
  el.tabButtons.querySelectorAll("button").forEach(button=>button.addEventListener("click",()=>{state.activeTab=button.dataset.tab;savePreferences();renderActiveTab();}));
  el.reviewState.addEventListener("change",()=>saveReview().catch(showFatal));el.confirmDraft.addEventListener("click",event=>confirmDraft(event).catch(showFatal));
  el.resetLayout.addEventListener("click",resetLayout);el.toggleDetail.addEventListener("click",()=>{state.detailCollapsed=!state.detailCollapsed;el.reviewWorkspace.classList.toggle("detail-collapsed",state.detailCollapsed);savePreferences();refreshResponsiveLayout();});
  el.layoutMode.addEventListener("change",()=>{state.layoutMode=el.layoutMode.value;applyReviewLayout();savePreferences();});
  el.reviewDensity.addEventListener("change",()=>{state.reviewDensity=Number(el.reviewDensity.value);applyReviewLayout();savePreferences();});
  setupSplitter(el.leftSplitter,"left");setupSplitter(el.rightSplitter,"right");setupSplitter(el.horizontalSplitter,"top");
  const workspaceObserver=new ResizeObserver(refreshResponsiveLayout);
  [el.reviewWorkspace,document.querySelector(".tree-pane"),document.querySelector(".center-pane"),el.detailPane,document.querySelector(".mapping-panel"),el.candidateTableContainer,document.querySelector(".evidence-panel"),el.tabButtons,el.tabContent,el.leftSplitter,el.rightSplitter,el.horizontalSplitter].filter(Boolean).forEach(node=>workspaceObserver.observe(node));
  window.addEventListener("resize",refreshResponsiveLayout);document.addEventListener("fullscreenchange",refreshResponsiveLayout);
}

const workbench=new QuotaReviewWorkbench(provider,state);
workbench.start().catch(showFatal);
