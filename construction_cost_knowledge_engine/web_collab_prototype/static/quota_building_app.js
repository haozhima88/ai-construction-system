const state = {
  summary: null, bills: [], selectedBill: null, billPayload: null, rows: [], selectedRow: null,
  evidence: null, activeTab: "resources", searchBillCodes: null, searchTimer: null,
  detail: null, tabData: {}, pendingAction: null, pdfZoom: "page-width", pdfPageOverride: null,
  textViewModes: {work:"structured", rules:"structured", conversions:"structured", notes:"structured"},
};

const el = Object.fromEntries([
  "summaryPill","draftStatsPill","treeMeta","treeSearchInput","treeFilter","priorityFilter","searchResults","treeRoot",
  "mainTitle","mainMeta","priorityPill","reviewSelect","exportCurrentBtn","mainRows","tabMeta","tabContent",
  "billDetails","quotaDetails","mappingDetails","technicalDetails","detailMeta","draftDialog","draftDialogTitle",
  "dialogSource","dialogQuota","targetWrap","targetBill","draftReason","confirmDraftBtn",
  "quotaWorkspace","leftSplitter","rightSplitter","horizontalSplitter","resetLayoutBtn",
].map(id => [id, document.getElementById(id)]));

function empty(value) { return value === null || value === undefined || value === "" ? "—" : String(value); }
function html(value) { return empty(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;"); }
function money(value) { const n = Number(value); return value === "" || value === null || Number.isNaN(n) ? "—" : n.toLocaleString("zh-CN", {minimumFractionDigits:2, maximumFractionDigits:2}); }
function fileName(path) { return String(path || "").split(/[\\/]/).pop() || "—"; }
function clamp(value, minimum, maximum) { return Math.min(maximum, Math.max(minimum, value)); }
function simplifiedAppendixName(name, code) {
  return String(name || "").replace(new RegExp(`^\\s*附录\\s*${String(code || "").replace(/[.*+?^${}()|[\\]\\]/g,"\\$&")}\\s*`, "i"), "").trim() || String(name || "");
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}
function post(path, payload) { return api(path, {method:"POST", body:JSON.stringify(payload)}); }

function badge(value) {
  const text = String(value || "pending"); let cls = "pending";
  if (/high|exclude|mismatch|P0/i.test(text)) cls = "high";
  else if (/low|direct|reviewed_candidate|P2/i.test(text)) cls = "low";
  else if (/manual|P1/i.test(text)) cls = "manual";
  return `<span class="badge ${cls}">${html(text)}</span>`;
}
function priorityBadge(value) { return `<span class="priority ${html(value)}">${html(value)}</span>`; }
function detailRows(fields) { return fields.map(([label,value,renderAsHtml=false]) => `<div class="detail-row"><div class="detail-label">${html(label)}</div><div class="detail-value">${renderAsHtml?value:html(value)}</div></div>`).join(""); }

function visibleBills() {
  const filter = el.treeFilter.value, priority = el.priorityFilter.value;
  return state.bills.filter(bill => {
    if (state.searchBillCodes && !state.searchBillCodes.has(bill.bill_code_9)) return false;
    if (priority !== "all" && bill.review_priority !== priority) return false;
    if (filter === "has_candidate" && Number(bill.original_count) === 0) return false;
    if (filter === "zero_candidate" && Number(bill.original_count) !== 0) return false;
    if (filter === "high_risk" && bill.review_priority !== "P0") return false;
    if (filter === "has_issue" && !bill.has_issue) return false;
    if (filter === "manual_review" && Number(bill.manual_review_count) === 0) return false;
    if (filter === "reviewed_candidate" && bill.review_state !== "reviewed_candidate") return false;
    if (filter === "needs_followup" && bill.review_state !== "needs_followup") return false;
    if (filter === "reviewed_mismatch" && bill.review_state !== "reviewed_mismatch") return false;
    return true;
  });
}

function groupedBills(items) {
  const result = new Map();
  items.forEach(bill => {
    if (!result.has(bill.appendix_code)) result.set(bill.appendix_code,{name:bill.appendix_name,sections:new Map()});
    const appendix = result.get(bill.appendix_code);
    if (!appendix.sections.has(bill.section_code)) appendix.sections.set(bill.section_code,{name:bill.section_name,bills:[]});
    appendix.sections.get(bill.section_code).bills.push(bill);
  });
  return result;
}

function countBadge(cls, value, title) { return Number(value) ? `<span class="count ${cls}" title="${title} ${value}">${value}</span>` : ""; }
function renderTree() {
  const items = visibleBills(); el.treeMeta.textContent = `${items.length} / ${state.bills.length} bill`;
  const grouped = groupedBills(items);
  el.treeRoot.innerHTML = [...grouped.entries()].map(([appendixCode, appendix]) => `
    <div class="tree-group"><button type="button" data-appendix-code="${html(appendixCode)}" title="附录${html(appendixCode)} ${html(appendix.name)}"><span>▾</span><span class="tree-label">${html(simplifiedAppendixName(appendix.name, appendixCode))}</span><span>${[...appendix.sections.values()].reduce((n,s)=>n+s.bills.length,0)}</span></button>
      <div>${[...appendix.sections.entries()].map(([sectionCode, section]) => `
        <div class="tree-section"><button type="button"><span>▾</span><span class="tree-label">${html(sectionCode)} ${html(section.name)}</span><span>${section.bills.length}</span></button>
          <div>${section.bills.map(bill => `<button class="tree-item ${state.selectedBill?.bill_code_9===bill.bill_code_9?"active":""}" data-bill="${html(bill.bill_code_9)}" title="${html(bill.bill_code_9)} ${html(bill.bill_name)} · ${html(bill.priority_reason)}"><span>·</span><span class="tree-label">${html(bill.bill_code_9)} ${html(bill.bill_name)}</span><span class="tree-counts">${priorityBadge(bill.review_priority)}${countBadge("original",bill.original_count,"original")}${countBadge("copy",Number(bill.copy_count)+Number(bill.copy_in_count),"copy")}${countBadge("move-in",bill.move_in_count,"move_in")}${countBadge("move-out",bill.move_out_count,"move_out")}${countBadge("exclude",bill.exclude_count,"exclude")}${countBadge("effective",bill.effective_count,"effective")}${countBadge("manual",bill.manual_review_count,"manual_review")}</span></button>`).join("")}</div>
        </div>`).join("")}</div>
    </div>`).join("") || `<div class="empty-row">没有符合条件的清单</div>`;
  el.treeRoot.querySelectorAll(".tree-item").forEach(button => button.addEventListener("click", () => selectBill(button.dataset.bill)));
  el.treeRoot.querySelectorAll(".tree-group>button,.tree-section>button").forEach(button => button.addEventListener("click", () => { const body=button.nextElementSibling; body.hidden=!body.hidden; button.firstElementChild.textContent=body.hidden?"▸":"▾"; }));
}

async function loadAll() {
  const [summary, tree] = await Promise.all([api("/api/quota-building/summary"), api("/api/quota-building/tree")]);
  state.summary=summary; state.bills=tree.items;
  el.summaryPill.textContent=`${summary.bill_count} bill / ${summary.quota_count} quota / ${summary.mapping_edge_count} edge`;
  el.draftStatsPill.textContent=`Draft ${summary.draft_count} / Audit ${summary.audit_count}`;
  renderTree();
}

async function performSearch() {
  const query=el.treeSearchInput.value.trim();
  if (!query) { state.searchBillCodes=null; el.searchResults.classList.remove("visible"); renderTree(); return; }
  const result=await api(`/api/quota-building/search?q=${encodeURIComponent(query)}`);
  state.searchBillCodes=new Set(result.bill_codes);
  const types=[...new Set(result.items.map(item=>item.match_type))].join(" / ");
  el.searchResults.textContent=`命中 ${result.bill_codes.length} 个清单 · ${types||"无结果"}`; el.searchResults.classList.add("visible"); renderTree();
}

async function selectBill(code) {
  const [payload,evidence]=await Promise.all([api(`/api/quota-building/bill/${encodeURIComponent(code)}/rows`),api(`/api/quota-building/bill/${encodeURIComponent(code)}/evidence`)]);
  state.selectedBill=state.bills.find(item=>item.bill_code_9===code)||payload.bill; state.billPayload=payload; state.rows=payload.rows; state.evidence=evidence;
  state.selectedRow=null; state.detail=null; state.tabData={}; state.activeTab="resources";
  el.mainTitle.textContent=`${payload.bill.bill_code_9} ${payload.bill.bill_name}`;
  el.mainMeta.textContent=`附录${payload.bill.appendix_code} · ${payload.bill.section_code} ${payload.bill.section_name} · ${payload.bill.unit||"单位待核"}`;
  el.priorityPill.textContent=`${state.selectedBill.review_priority} · ${state.selectedBill.priority_reason}`;
  el.priorityPill.className=`status-pill ${state.selectedBill.review_priority==="P0"?"danger":state.selectedBill.review_priority==="P1"?"warn":""}`;
  el.reviewSelect.disabled=false; el.reviewSelect.value=state.selectedBill.review_state||"not_reviewed";
  el.exportCurrentBtn.classList.remove("disabled"); el.exportCurrentBtn.href=`/api/quota-building/export/current/${code}`;
  renderTree(); renderMainRows(); renderBillDetails();
  if (state.rows.length) await selectRow(state.rows[0]); else renderEmptyQuota();
}

function renderMainRows() {
  if (!state.billPayload) return;
  const bill=state.billPayload.bill;
  const master=`<tr class="bill-master"><td>B1</td><td>${badge("清单")}</td><td>${html(bill.bill_code_9)}</td><td>${html(bill.bill_name)}<span class="secondary">${html(bill.project_feature_raw)}</span></td><td>${html(bill.unit)}</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>GB/T bill</td><td>${badge(state.evidence?.evidence?.authority_verification_status||"pending_evidence_link")}</td><td>${badge(state.selectedBill.review_state)}</td><td>${priorityBadge(state.selectedBill.review_priority)}</td><td>—</td></tr>`;
  const candidates=state.rows.map((item,index)=>`<tr class="${item.effective?"":"ineffective"} ${state.selectedRow?.mapping_edge_id===item.mapping_edge_id&&state.selectedRow?.row_origin===item.row_origin?"selected":""}" data-index="${index}"><td>${index+1}</td><td>${badge(`${item.row_origin?.startsWith("draft")?"Draft":"定额"}/${item.volume_code}`)}</td><td>${html(item.source_code)}</td><td>${html(item.quota_name)}</td><td>${html(item.quota_unit)}</td><td>${money(item.labor_fee)}</td><td>${money(item.material_fee)}</td><td>${money(item.machine_fee)}</td><td>${money(item.management_fee)}</td><td>${money(item.total_fee)}</td><td>${html(item.mapping_role)}</td><td>${badge(item.effective?"candidate":"hidden")}</td><td>${badge(item.review_status)}</td><td>${priorityBadge(item.review_priority)} ${badge(item.risk_level)}</td><td><div class="row-actions">${item.draft_id?`<button class="icon-button" data-action="restore" title="Restore">↶</button>`:`<button class="icon-button" data-action="copy" title="Copy">⧉</button><button class="icon-button" data-action="move" title="Move">⇥</button><button class="icon-button" data-action="exclude" title="Exclude">×</button>`}</div></td></tr>`).join("");
  el.mainRows.innerHTML=master+(candidates||`<tr><td colspan="15" class="empty-row">该清单无自动候选，保留人工审核</td></tr>`);
  el.mainRows.querySelectorAll("tr[data-index]").forEach(tr=>{
    tr.addEventListener("click",event=>{if(!event.target.closest("button"))selectRow(state.rows[Number(tr.dataset.index)])});
    tr.querySelectorAll("button").forEach(button=>button.addEventListener("click",event=>{event.stopPropagation();handleDraft(button.dataset.action,state.rows[Number(tr.dataset.index)])}));
  });
}

function renderBillDetails() {
  const bill=state.billPayload?.bill||{}, evidence=state.evidence?.evidence||{};
  el.billDetails.innerHTML=detailRows([["编码",bill.bill_code_9],["名称",bill.bill_name],["单位",bill.unit],["项目特征",bill.project_feature_raw],["工作内容",bill.work_content_raw],["工程量规则",bill.quantity_calculation_rule],["PDF证据",`<div class="detail-badge-group">${badge(evidence.authority_verification_status||"pending_evidence_link")}</div>`,true]]);
}
function renderEmptyQuota(){el.quotaDetails.innerHTML=detailRows([["状态","无自动候选"]]);el.mappingDetails.innerHTML="";el.technicalDetails.innerHTML="";el.tabContent.innerHTML=`<div class="empty-row">当前清单无省定额候选</div>`}

async function selectRow(item) {
  state.selectedRow=item; state.activeTab="resources"; state.pdfZoom="page-width"; state.pdfPageOverride=null; renderMainRows();
  const base=`/api/quota-building/quota/${encodeURIComponent(item.quota_uid)}`;
  const [detail,resources,work,rules,conversions,notes,issues]=await Promise.all([api(`${base}/detail`),api(`${base}/resources`),api(`${base}/work-content`),api(`${base}/quantity-rules`),api(`${base}/conversions`),api(`${base}/notes`),api(`${base}/issues`)]);
  state.detail=detail; state.tabData={resources,work,rules,conversions,notes,issues};
  renderQuotaDetails(resources.count,work.count,rules.count); renderTab();
}

function renderQuotaDetails(resourceCount,workCount,ruleCount) {
  const item=state.selectedRow, quota=state.detail?.quota||{}, price=state.detail?.price||{};
  el.detailMeta.textContent=`${item.volume_code} / PDF ${item.quota_pdf_page_no}`;
  el.quotaDetails.innerHTML=detailRows([["编码",item.source_code],["名称",quota.raw_name],["册次",`${quota.volume_code} ${quota.volume_name}`],["章节",`${quota.chapter_code} / ${quota.section_code}`],["单位",quota.unit_normalized],["PDF页",quota.pdf_page_no],["资源数",resourceCount],["费用构成",`人工 ${money(price.labor_fee)} / 材料 ${money(price.material_fee)} / 机具 ${money(price.machine_fee)} / 管理 ${money(price.management_fee)} / 基价 ${money(price.total_fee)}`],["Scope",`工作内容 ${workCount} / 规则 ${ruleCount}`]]);
  el.mappingDetails.innerHTML=detailRows([["角色",item.mapping_role],["Routing",item.routing_class],["风险",`<div class="detail-badge-group">${priorityBadge(item.review_priority)}${badge(item.risk_level)}</div>`,true],["解释",item.ai_mapping_explanation],["Draft状态",`<div class="detail-badge-group">${badge(item.draft_status||"none")}</div>`,true],["Review状态",`<div class="detail-badge-group">${badge(item.review_status)}</div>`,true],["审核优先级",`${item.review_priority} · ${item.priority_reason}`]]);
  el.technicalDetails.innerHTML=detailRows([["source_document_id",quota.source_document_id],["quota_uid",quota.quota_uid],["mapping_edge_id",item.mapping_edge_id],["完整路径",quota.source_file],["完整Hash",quota.source_sha256]]);
}

function activateTab(name){state.activeTab=name;renderTab()}
function renderTab(){
  document.querySelectorAll(".tab-button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.activeTab));
  const item=state.selectedRow; el.tabMeta.textContent=item?`${item.source_code} ${item.quota_name}`:"请选择省定额候选";
  if(state.activeTab==="v1v2")return loadGlobalTab("v1v2","/api/quota-building/v1-v2");
  if(state.activeTab==="audit")return loadGlobalTab("audit","/api/quota-building/audit");
  if(!item){el.tabContent.innerHTML=`<div class="empty-row">请选择省定额候选</div>`;return}
  if(state.activeTab==="resources")return renderResources(state.tabData.resources?.items||[]);
  if(state.activeTab==="work")return renderStructuredTextTab("work",state.tabData.work?.items||[],"content_text","工作内容");
  if(state.activeTab==="rules")return renderStructuredTextTab("rules",state.tabData.rules?.items||[],"rule_text","工程量规则");
  if(state.activeTab==="province-pdf")return renderProvincePdf();
  if(state.activeTab==="price")return renderPrice();
  if(state.activeTab==="conversions")return renderStructuredTextTab("conversions",state.tabData.conversions?.items||[],"source_text_raw","换算规则");
  if(state.activeTab==="notes")return renderStructuredTextTab("notes",state.tabData.notes?.items||[],"clause_text","注释");
  if(state.activeTab==="authority")return renderAuthorityPdf();
  if(state.activeTab==="mapping")return renderMappingExplanation();
  if(state.activeTab==="issues"){const data=[...(state.tabData.issues?.items||[]),...(state.tabData.issues?.mapping_items||[])];return renderGeneric(data)}
}

function renderResources(items){
  if(!items.length){el.tabContent.innerHTML=`<div class="empty-row">无工料机记录</div>`;return}
  const cols=[["resource_code","编码"],["resource_name","名称"],["resource_category","类别"],["unit","单位"],["consumption","含量"],["unit_price","单价"],["amount","合价"]];
  el.tabContent.innerHTML=tableHtml(items,cols);
}
function markerLevel(marker, fallback="条款") {
  if (/^[一二三四五六七八九十]+、$/.test(marker)) return "分部";
  if (/^[（(]/.test(marker)) return "子项";
  if (/^\d+[.、]$/.test(marker)) return "条款";
  if (/^注/.test(marker)) return "注";
  if (/^表/.test(marker)) return "表";
  return fallback;
}

function hierarchyLabel(row) {
  const labels={raw:"总则",page_block:"总则",section:"分部",subsection:"子项",clause:"条款",note:"注",table:"表"};
  return labels[String(row?.hierarchy_level||"").toLowerCase()]||markerLevel(String(row?.rule_number||""),"原记录");
}
function splitMarkedText(text, fallbackNo="", fallbackLevel="原记录") {
  const source=String(text||"").replace(/\s+/g," ").trim();
  if(!source)return [];
  const markerPattern=/(^|[\s。；;：:])((?:[一二三四五六七八九十]+、)|(?:[（(][一二三四五六七八九十0-9]+[）)])|(?:\d{1,2}[.、](?=\s*[\u4e00-\u9fffA-Za-z]))|(?:注(?:释)?[:：]?)|(?:表(?:[一二三四五六七八九十]|\d+|-\d+)?(?=\s)))/gu;
  const matches=[...source.matchAll(markerPattern)].map(match=>({index:match.index+match[1].length,marker:match[2]}));
  if(!matches.length)return [{level:fallbackLevel,number:fallbackNo||"—",content:source}];
  const result=[];
  const prefix=source.slice(0,matches[0].index).trim().replace(/^\d+\s+(?:说\s*明|工程量计算规则)\s*/,"").trim();
  if(prefix)result.push({level:fallbackLevel,number:fallbackNo||"总则",content:prefix});
  matches.forEach((match,index)=>{
    const next=matches[index+1]?.index??source.length;
    const content=source.slice(match.index+match.marker.length,next).trim();
    if(content)result.push({level:markerLevel(match.marker),number:match.marker,content});
  });
  return result.length?result:[{level:fallbackLevel,number:fallbackNo||"—",content:source}];
}

function structuredRows(kind,items,field) {
  let sequence=0;
  return items.flatMap((row,rowIndex)=>{
    const fallback=kind==="rules"?(row.rule_number||row.rule_title||String(rowIndex+1)):String(rowIndex+1);
    const parts=splitMarkedText(row[field],fallback,kind==="rules"?hierarchyLabel(row):"原记录");
    return parts.map(part=>{
      sequence+=1;
      return {seq_no:sequence,level:part.level,rule_no:part.number,content:part.content,pdf_page:row.pdf_page_no||row.page_start||"—"};
    });
  });
}

function pdfPageButton(page) { return `<button class="pdf-page-link" type="button" data-pdf-page="${html(page)}" title="查看原文 PDF">P${html(page)} <span aria-hidden="true">↗</span></button>`; }
function structuredTable(kind,rows) {
  const columns=kind==="work"?[["seq_no","序号","col-number"],["content","内容",""],["pdf_page","PDF页","col-page"]]:kind==="rules"?[["level","层级","col-level"],["rule_no","规则号","col-number"],["content","内容",""],["pdf_page","PDF页","col-page"]]:kind==="notes"?[["rule_no","注释序号","col-number"],["content","内容",""],["pdf_page","PDF页","col-page"]]:[["rule_no","规则号","col-number"],["content","内容",""],["pdf_page","PDF页","col-page"]];
  return `<table class="data-table structured-table"><colgroup>${columns.map(([, ,cls])=>`<col class="${cls}">`).join("")}</colgroup><thead><tr>${columns.map(([,label])=>`<th>${html(label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr>${columns.map(([key])=>`<td>${key==="pdf_page"?pdfPageButton(row[key]):html(row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function rawTextView(items,field,title) {
  return `<div class="raw-view">${items.map((row,index)=>`<article class="raw-record"><div class="raw-record-head"><strong>${html(title)}原文 ${index+1}</strong>${pdfPageButton(row.pdf_page_no||row.page_start||"—")}</div><div class="raw-record-text">${html(row[field])}</div></article>`).join("")}</div>`;
}
function bindTextViewActions(kind) {
  el.tabContent.querySelectorAll("button[data-text-mode]").forEach(button=>button.addEventListener("click",()=>{state.textViewModes[kind]=button.dataset.textMode;renderTab()}));
  el.tabContent.querySelectorAll("button[data-pdf-page]").forEach(button=>button.addEventListener("click",()=>{state.pdfPageOverride=button.dataset.pdfPage;activateTab("province-pdf")}));
}
function renderStructuredTextTab(kind,items,field,title) {
  if(!items.length){el.tabContent.innerHTML=`<div class="empty-row">无${title}记录</div>`;return}
  const rows=structuredRows(kind,items,field),mode=state.textViewModes[kind]||"structured";
  el.tabContent.innerHTML=`<div class="text-view"><div class="text-view-toolbar"><div class="segmented-control" role="group" aria-label="${html(title)}视图"><button type="button" data-text-mode="structured" class="${mode==="structured"?"active":""}">结构化视图</button><button type="button" data-text-mode="raw" class="${mode==="raw"?"active":""}">原文视图</button></div><span class="text-view-meta">${mode==="structured"?`${rows.length} 条结构记录`:`${items.length} 条原始记录`}</span></div>${mode==="structured"?structuredTable(kind,rows):rawTextView(items,field,title)}</div>`;
  bindTextViewActions(kind);
}
function tableHtml(items,cols){return `<table class="data-table"><thead><tr>${cols.map(([,label])=>`<th>${html(label)}</th>`).join("")}</tr></thead><tbody>${items.map(row=>`<tr>${cols.map(([key])=>`<td>${html(row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function renderGeneric(items){if(!items.length){el.tabContent.innerHTML=`<div class="empty-row">当前作用域无记录</div>`;return}const keys=Object.keys(items[0]).filter(k=>k!=="scope").slice(0,12);el.tabContent.innerHTML=tableHtml(items,keys.map(k=>[k,k]))}
function renderPrice(){const p=state.detail?.price||{};el.tabContent.innerHTML=tableHtml([p],[["labor_fee","人工"],["material_fee","材料"],["machine_fee","机具"],["management_fee","管理"],["other_fee","其他"],["total_fee","基价"],["price_unit","计价单位"]])}

function renderProvincePdf(){
  const q=state.detail.quota,page=state.pdfPageOverride||q.pdf_page_no||1,zoom=state.pdfZoom;
  const src=`/api/quota-building/pdf/province/${q.volume_code}#page=${page}&zoom=${zoom}`;
  el.tabContent.innerHTML=`<div class="pdf-viewer"><div class="pdf-toolbar"><strong>${html(q.volume_code)} ${html(q.volume_name)}</strong><span class="file-meta">${html(fileName(q.source_file))} · PDF ${html(page)} · ${html(String(q.source_sha256||"").slice(0,12))}…</span><button data-zoom="out" title="缩小">−</button><button data-zoom="fit" title="适合宽度">↔</button><button data-zoom="in" title="放大">＋</button></div><iframe class="pdf-frame" title="省定额 PDF 原页" src="${src}"></iframe></div>`;
  bindPdfZoom(renderProvincePdf);
}
function renderAuthorityPdf(){
  const evidence=state.evidence?.evidence||{},page=evidence.authority_pdf_page_no||"",fragment=page?`#page=${page}&zoom=${state.pdfZoom}`:`#zoom=${state.pdfZoom}`;
  const status=page?evidence.authority_verification_status:"官方PDF页证据待补";
  el.tabContent.innerHTML=`<div class="pdf-viewer"><div class="pdf-toolbar"><strong>authority source · 官方 GB/T 50854 PDF</strong><span class="file-meta">extraction proxy: DOCX · baseline: 472 derived pending reference · ${html(status)}</span><button data-zoom="out" title="缩小">−</button><button data-zoom="fit" title="适合宽度">↔</button><button data-zoom="in" title="放大">＋</button></div><iframe class="pdf-frame" title="国家标准 PDF" src="/api/quota-building/pdf/authority${fragment}"></iframe></div>`;
  bindPdfZoom(renderAuthorityPdf);
}
function bindPdfZoom(render){el.tabContent.querySelectorAll("button[data-zoom]").forEach(button=>button.addEventListener("click",()=>{const action=button.dataset.zoom,current=Number(state.pdfZoom)||100;state.pdfZoom=action==="fit"?"page-width":action==="in"?Math.min(current+20,200):Math.max(current-20,40);render()}))}
function renderMappingExplanation(){const i=state.selectedRow;el.tabContent.innerHTML=`<div class="text-list"><div class="text-record"><strong>Mapping 解释</strong><br>${html(i.ai_mapping_explanation)}</div><div class="text-record"><strong>风险与审核队列</strong><br>${html(i.risk_reason)}<br>${html(i.review_priority)} · ${html(i.priority_reason)}</div><div class="text-record"><strong>算法字段</strong><br>semantic ${html(i.semantic_score)} · chapter ${html(i.chapter_score)} · name ${html(i.name_score)} · work ${html(i.work_content_score)} · feature ${html(i.feature_score)} · rule ${html(i.quantity_rule_score)} · unit ${html(i.unit_compatibility)}</div></div>`}
async function loadGlobalTab(key,url){if(!state.tabData[key])state.tabData[key]=await api(url);renderGeneric(state.tabData[key].items||[])}

function handleDraft(action,item){
  if(action==="restore")return restoreDraft(item.draft_id);
  state.pendingAction={action,item};el.draftDialogTitle.textContent={copy:"Copy Candidate",move:"Move Candidate",exclude:"Exclude Candidate"}[action];
  el.dialogSource.textContent=`${state.selectedBill.bill_code_9} ${state.selectedBill.bill_name}`;el.dialogQuota.textContent=`${item.source_code} ${item.quota_name}`;el.targetWrap.hidden=action==="exclude";
  el.targetBill.innerHTML=state.bills.filter(b=>b.bill_code_9!==state.selectedBill.bill_code_9).map(b=>`<option value="${b.bill_code_9}">${b.bill_code_9} ${html(b.bill_name)}</option>`).join("");el.draftReason.value="";el.draftDialog.showModal();
}
async function saveDraft(event){event.preventDefault();const {action,item}=state.pendingAction;await post("/api/quota-building/draft/action",{source_edge_id:item.mapping_edge_id,target_bill_code_9:action==="exclude"?"":el.targetBill.value,action_type:action,operation_reason:el.draftReason.value});el.draftDialog.close();const code=state.selectedBill.bill_code_9;await loadAll();await selectBill(code)}
async function restoreDraft(id){await post(`/api/quota-building/draft/${id}/restore`,{});const code=state.selectedBill.bill_code_9;await loadAll();await selectBill(code)}
async function saveReview(){if(!state.selectedBill)return;await post("/api/quota-building/review-state",{bill_code_9:state.selectedBill.bill_code_9,quota_uid:"",review_status:el.reviewSelect.value,comment:""});const code=state.selectedBill.bill_code_9;await loadAll();await selectBill(code)}

const LAYOUT_STORAGE_KEY="quotaBuildingReviewLayoutV1";
let layoutState=null;
function defaultLayout() {
  const centerHeight=document.querySelector(".center-shell")?.getBoundingClientRect().height||Math.max(470,window.innerHeight-58);
  return {treeWidth:320,detailWidth:clamp(window.innerWidth*.22,340,420),mainHeight:Math.round(centerHeight*.58)};
}
function constrainedLayout(candidate) {
  const workspaceWidth=el.quotaWorkspace.getBoundingClientRect().width||window.innerWidth;
  const treeWidth=clamp(Number(candidate.treeWidth)||320,280,Math.max(280,Math.min(440,workspaceWidth-800)));
  const detailWidth=clamp(Number(candidate.detailWidth)||380,320,Math.max(320,Math.min(480,workspaceWidth-treeWidth-480)));
  const centerHeight=document.querySelector(".center-shell")?.getBoundingClientRect().height||Math.max(470,window.innerHeight-58);
  const mainHeight=clamp(Number(candidate.mainHeight)||Math.round(centerHeight*.58),260,Math.max(260,centerHeight-216));
  return {treeWidth,detailWidth,mainHeight};
}
function applyLayout(candidate,{persist=false}={}) {
  layoutState=constrainedLayout(candidate);
  el.quotaWorkspace.style.setProperty("--tree-pane-width",`${layoutState.treeWidth}px`);
  el.quotaWorkspace.style.setProperty("--detail-pane-width",`${layoutState.detailWidth}px`);
  el.quotaWorkspace.style.setProperty("--main-pane-height",`${layoutState.mainHeight}px`);
  el.leftSplitter.setAttribute("aria-valuenow",Math.round(layoutState.treeWidth));
  el.rightSplitter.setAttribute("aria-valuenow",Math.round(layoutState.detailWidth));
  el.horizontalSplitter.setAttribute("aria-valuenow",Math.round(layoutState.mainHeight));
  if(persist){localStorage.setItem(LAYOUT_STORAGE_KEY,JSON.stringify(layoutState));document.documentElement.dataset.layoutPersisted="true"}
}
function loadLayout() {
  try {
    const stored=JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY)||"null");
    applyLayout(stored||defaultLayout());
    document.documentElement.dataset.layoutPersisted=stored?"true":"false";
  } catch(error) {
    localStorage.removeItem(LAYOUT_STORAGE_KEY);applyLayout(defaultLayout());document.documentElement.dataset.layoutPersisted="false";
  }
}
function bindSplitter(handle,axis) {
  handle.addEventListener("pointerdown",event=>{
    if(event.button!==0)return;
    event.preventDefault();handle.setPointerCapture(event.pointerId);handle.classList.add("dragging");document.body.classList.add("layout-resizing");
    const start={x:event.clientX,y:event.clientY,...layoutState};
    const move=moveEvent=>{
      if(axis==="left")applyLayout({...start,treeWidth:start.treeWidth+moveEvent.clientX-start.x});
      if(axis==="right")applyLayout({...start,detailWidth:start.detailWidth-(moveEvent.clientX-start.x)});
      if(axis==="horizontal")applyLayout({...start,mainHeight:start.mainHeight+moveEvent.clientY-start.y});
    };
    const finish=()=>{handle.classList.remove("dragging");document.body.classList.remove("layout-resizing");handle.removeEventListener("pointermove",move);handle.removeEventListener("pointerup",finish);handle.removeEventListener("pointercancel",finish);applyLayout(layoutState,{persist:true})};
    handle.addEventListener("pointermove",move);handle.addEventListener("pointerup",finish);handle.addEventListener("pointercancel",finish);
  });
  handle.addEventListener("keydown",event=>{
    const direction=event.key==="ArrowRight"||event.key==="ArrowDown"?1:event.key==="ArrowLeft"||event.key==="ArrowUp"?-1:0;
    if(!direction)return;
    event.preventDefault();
    if(axis==="left")applyLayout({...layoutState,treeWidth:layoutState.treeWidth+direction*10},{persist:true});
    if(axis==="right")applyLayout({...layoutState,detailWidth:layoutState.detailWidth-direction*10},{persist:true});
    if(axis==="horizontal")applyLayout({...layoutState,mainHeight:layoutState.mainHeight+direction*10},{persist:true});
  });
}
function initializeLayout() {
  loadLayout();bindSplitter(el.leftSplitter,"left");bindSplitter(el.rightSplitter,"right");bindSplitter(el.horizontalSplitter,"horizontal");
  el.resetLayoutBtn.addEventListener("click",()=>{localStorage.removeItem(LAYOUT_STORAGE_KEY);applyLayout(defaultLayout());document.documentElement.dataset.layoutPersisted="false"});
  window.addEventListener("resize",()=>applyLayout(layoutState||defaultLayout()));
}

el.treeSearchInput.addEventListener("input",()=>{clearTimeout(state.searchTimer);state.searchTimer=setTimeout(()=>performSearch().catch(showFatal),220)});el.treeFilter.addEventListener("change",renderTree);el.priorityFilter.addEventListener("change",renderTree);el.reviewSelect.addEventListener("change",()=>saveReview().catch(showFatal));el.confirmDraftBtn.addEventListener("click",event=>saveDraft(event).catch(showFatal));document.querySelectorAll(".tab-button").forEach(button=>button.addEventListener("click",()=>activateTab(button.dataset.tab)));
function showFatal(error){console.error(error);el.tabContent.innerHTML=`<div class="empty-row">${html(error.message)}</div>`}
initializeLayout();
loadAll().catch(showFatal);
