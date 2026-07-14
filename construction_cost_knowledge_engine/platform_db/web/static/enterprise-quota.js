"use strict";

const state={
  me:null,summary:null,tree:[],detail:null,priceItems:[],priceFilter:"all",priceThreshold:"20",
  activeTab:"composition",mode:"view",buffer:null,activeCell:null,editingCell:null,
  validationErrors:new Map(),saving:false,savedKeys:new Set(),serverConflictDetail:null,
  pendingNavigation:null,drawerMode:null,drawerRow:null,savedMessage:null,
};
const $=id=>document.getElementById(id);
const esc=value=>String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const fmt=value=>value===null||value===undefined||value===""?"—":String(value);
const can=permission=>state.me?.permissions?.includes(permission);
const clone=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value));
const same=(left,right)=>JSON.stringify(left??null)===JSON.stringify(right??null);
const statusText=value=>({
  provincial_reference_fallback:"省定额回填",enterprise_manual_price:"企业人工价",
  provincial_reference_price_missing:"省定额价缺失",pending_manual_pricing:"待人工核价",
  reviewed_fallback_accepted:"已接受省定额",manual_price_draft:"人工价 Draft",
  manual_price_reviewed:"人工价已审核",returned_for_revision:"退回修改",
  quantity_unit_price:"数量×单价",direct_amount:"直接金额",rate_based:"费率计算",formula_based:"公式计算",
  inherited:"继承",quantity_modified:"消耗量已修改",amount_modified:"直接金额已修改",
  resource_added:"新增资源",resource_replaced:"已替换资源",resource_removed:"待移除",restored:"待恢复",
  specification_modified:"规格已修改",draft:"Draft",reviewed:"已审核",
}[value]||fmt(value));
const fieldText=value=>({
  enterprise_quantity:"企业消耗量",enterprise_direct_amount:"企业直接金额",
  enterprise_specification:"企业规格",component:"资源结构",lifecycle_status:"组件状态",
}[value]||value);

class DraftEditBuffer{
  constructor(quotaVersionId,baseRowVersion){
    this.quota_version_id=quotaVersionId;this.base_row_version=baseRowVersion;
    this.changes=new Map();this.history=[];this.local_sequence=0;
  }
  key(change){return `${change.component_id||change.client_component_id}:${change.field_name}`;}
  put(change){
    const key=this.key(change);const previous=this.changes.has(key)?clone(this.changes.get(key)):null;
    const original=previous?.before_value??change.before_value;
    if(!change.change_type.startsWith("resource_")&&change.change_type!=="restored"&&same(original,change.after_value)){
      if(previous){this.history.push({key,previous});this.changes.delete(key);}return;
    }
    this.history.push({key,previous});this.local_sequence+=1;
    this.changes.set(key,{
      quota_version_id:this.quota_version_id,base_row_version:this.base_row_version,
      component_id:change.component_id||null,client_component_id:change.client_component_id||null,
      field_name:change.field_name,before_value:clone(original),after_value:clone(change.after_value),
      change_type:change.change_type,reason:change.reason||"Excel式受控编辑",
      validation_status:change.validation_status||"valid",dirty:true,local_sequence:this.local_sequence,
    });
  }
  revert(key){if(!this.changes.has(key))return;this.history.push({key,previous:clone(this.changes.get(key))});this.changes.delete(key);}
  undo(){const item=this.history.pop();if(!item)return false;if(item.previous)this.changes.set(item.key,item.previous);else this.changes.delete(item.key);return true;}
  clear(){this.changes.clear();this.history=[];this.local_sequence=0;}
  get size(){return this.changes.size;}
  get dirty(){return this.size>0;}
  entries(){return [...this.changes.values()].sort((a,b)=>a.local_sequence-b.local_sequence);}
  payload(){return this.entries().map(({component_id,client_component_id,field_name,before_value,after_value,change_type,reason})=>({component_id,client_component_id,field_name,before_value,after_value,change_type,reason}));}
  rebase(detail){
    this.quota_version_id=detail.version.enterprise_quota_version_id;this.base_row_version=detail.version.row_version;
    const rows=new Map(detail.components.map(row=>[row.enterprise_quota_component_version_id,row]));
    for(const change of this.changes.values()){
      const row=rows.get(change.component_id);if(!row)continue;
      if(change.field_name==="enterprise_quantity")change.before_value=row.consumption;
      if(change.field_name==="enterprise_direct_amount")change.before_value=row.enterprise_direct_amount;
      if(change.field_name==="enterprise_specification")change.before_value=row.specification;
      change.base_row_version=this.base_row_version;change.validation_status="valid";
    }
  }
}

async function api(path,options={}){
  const headers={...(options.headers||{})};
  if(options.body){headers["Content-Type"]="application/json";headers["X-CSRF-Token"]=state.me.csrf_token;}
  const response=await fetch(path,{credentials:"same-origin",...options,headers});
  if(response.status===401){location.href=`/login?next=${encodeURIComponent(location.pathname)}`;throw new Error("需要登录");}
  const payload=await response.json().catch(()=>({detail:response.statusText}));
  if(!response.ok){
    const detail=payload.detail;const error=new Error(typeof detail==="string"?detail:(detail?.message||"请求失败"));
    error.status=response.status;error.payload=payload;throw error;
  }
  return payload;
}

function toast(message,error=false){
  const node=$("toast");node.textContent=message;node.className=`eq-toast show${error?" error":""}`;
  clearTimeout(node.timer);node.timer=setTimeout(()=>node.className="eq-toast",3200);
}

function decimalParts(value){
  const text=String(value??"0").trim();const match=text.match(/^([+-]?)(\d+)(?:\.(\d+))?$/);if(!match)return null;
  const fraction=match[3]||"";return {sign:match[1]==="-"?-1n:1n,digits:BigInt((match[2]+fraction).replace(/^0+(?=\d)/,"")),scale:fraction.length};
}
function scaledInteger(value,scale=6){
  const parsed=decimalParts(value);if(!parsed)return null;let digits=parsed.digits;
  if(parsed.scale<scale)digits*=10n**BigInt(scale-parsed.scale);
  else if(parsed.scale>scale){const divisor=10n**BigInt(parsed.scale-scale);digits=(digits+divisor/2n)/divisor;}
  return parsed.sign*digits;
}
function formatScaled(integer,scale=6){
  const sign=integer<0n?"-":"";let digits=(integer<0n?-integer:integer).toString().padStart(scale+1,"0");
  return `${sign}${digits.slice(0,-scale)}.${digits.slice(-scale)}`;
}
function decimalMultiply(left,right,scale=6){
  const a=decimalParts(left),b=decimalParts(right);if(!a||!b)return null;
  const raw=a.sign*b.sign*a.digits*b.digits;const rawScale=a.scale+b.scale;
  if(rawScale===scale)return formatScaled(raw,scale);
  if(rawScale<scale)return formatScaled(raw*10n**BigInt(scale-rawScale),scale);
  const divisor=10n**BigInt(rawScale-scale);const sign=raw<0n?-1n:1n;const rounded=(raw*sign+divisor/2n)/divisor*sign;
  return formatScaled(rounded,scale);
}
function decimalAdd(values,scale=6){let total=0n;for(const value of values){const item=scaledInteger(value,scale);if(item===null)return null;total+=item;}return formatScaled(total,scale);}
function decimalSubtract(left,right,scale=6){const a=scaledInteger(left,scale),b=scaledInteger(right,scale);return a===null||b===null?null:formatScaled(a-b,scale);}

function renderMetrics(){
  const s=state.summary;const items=[
    ["A1.1 Reference",s.a111_reference_quota_count],["企业 Draft",s.enterprise_quota_draft_count],
    ["定额可计算",s.enterprise_quota_calculation_coverage],["省价回填",s.provincial_fallback_price_count],
    ["待人工核价",s.pending_manual_pricing_count,"warn"],["计算价格覆盖",s.calculation_price_coverage],
    ["企业确认覆盖",s.enterprise_confirmed_price_coverage,"warn"],["批准 / 发布",`${s.approved_count} / ${s.published_count}`],
  ];
  $("metrics").innerHTML=items.map(([label,value,kind])=>`<div class="eq-metric ${kind||""}"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  $("priceCoverage").textContent=`计算覆盖 ${s.calculation_price_coverage} · 企业确认 ${s.enterprise_confirmed_price_coverage}`;
}

function renderTree(){
  const query=$("quotaSearch").value.trim().toLowerCase();const current=state.detail?.version?.enterprise_quota_version_id;
  $("quotaTree").innerHTML=state.tree.filter(row=>!query||`${row.source_quota_code} ${row.quota_name}`.toLowerCase().includes(query)).map(row=>`<button class="eq-tree-item ${row.enterprise_quota_version_id===current?"active":""}" data-version="${row.enterprise_quota_version_id}"><span class="eq-tree-code">${esc(row.source_quota_code)} · V${row.version_no}</span><span class="eq-tree-name">${esc(row.quota_name)}</span></button>`).join("");
  document.querySelectorAll(".eq-tree-item").forEach(button=>button.addEventListener("click",()=>guardNavigation(()=>loadDetail(button.dataset.version))));
}

function renderMeta(){
  const d=state.detail,r=d.reference,v=d.version;
  $("referenceMeta").innerHTML=[["来源版本",v.source_reference_release_id],["省定额编码",r.source_code],["省定额名称",r.quota_name],["PDF 页",r.pdf_page_no],["省定额基价",r.total_fee]].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(fmt(b))}</dd>`).join("");
  $("versionMeta").innerHTML=[["版本",`V${v.enterprise_quota_version_no}`],["状态",v.status],["源 Hash",v.source_quota_version_hash],["行版本",v.row_version],["计算规则",v.calculation_rule_version]].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(fmt(b))}</dd>`).join("");
}

function bufferChange(componentId,fieldName){
  if(!state.buffer)return null;return state.buffer.changes.get(`${componentId}:${fieldName}`)||null;
}
function baseRow(componentId){return state.detail.components.find(row=>row.enterprise_quota_component_version_id===componentId);}
function resource(resourceId){return state.priceItems.find(row=>row.enterprise_resource_id===resourceId);}

function projectedComponents(){
  const rows=state.detail.components.map(row=>({...row,_identity:row.enterprise_quota_component_version_id,_changed:false}));
  const byId=new Map(rows.map(row=>[row._identity,row]));
  for(const change of state.buffer?.entries()||[]){
    if(change.change_type==="resource_added"){
      const data=change.after_value;const selected=resource(data.enterprise_resource_id)||{};
      const row={
        enterprise_quota_component_version_id:change.client_component_id,_identity:change.client_component_id,
        _clientAdded:true,_changed:true,line_no:rows.length+1,enterprise_resource_id:data.enterprise_resource_id,
        source_enterprise_resource_id:null,source_reference_resource_id:null,resource_code:selected.resource_code,
        resource_name:selected.resource_name,specification:data.enterprise_specification||selected.specification,
        master_specification:selected.specification,unit:selected.unit,resource_category:selected.resource_category,
        calculation_basis:data.calculation_basis,source_consumption:null,consumption:data.enterprise_quantity??null,
        enterprise_direct_amount:data.enterprise_direct_amount??null,provincial_unit_price:null,
        selected_enterprise_price:selected.selected_price,provincial_component_amount:null,component_status:"resource_added",
        lifecycle_status:"active",amount_source:data.calculation_basis,row_version:1,
      };rows.push(row);byId.set(row._identity,row);continue;
    }
    const row=byId.get(change.component_id);if(!row)continue;row._changed=true;
    if(change.change_type==="quantity_modified")row.consumption=change.after_value;
    if(change.change_type==="amount_modified")row.enterprise_direct_amount=change.after_value;
    if(change.change_type==="specification_modified")row.specification=change.after_value||row.master_specification;
    if(change.change_type==="resource_removed"){row._pendingRemove=true;row.lifecycle_status="removed";row.component_status="resource_removed";}
    if(change.change_type==="restored"){
      const selected=resource(row.source_enterprise_resource_id)||{};row._pendingRestore=true;row.lifecycle_status="active";row.component_status="restored";
      row.enterprise_resource_id=row.source_enterprise_resource_id;row.resource_code=selected.resource_code||row.resource_code;
      row.resource_name=selected.resource_name||row.resource_name;row.specification=selected.specification;row.unit=selected.unit||row.unit;
      row.resource_category=selected.resource_category||row.resource_category;row.consumption=row.source_consumption;
      row.enterprise_direct_amount=row.source_direct_amount;row.selected_enterprise_price=selected.selected_price;
    }
    if(change.change_type==="resource_replaced"){
      const data=change.after_value,selected=resource(data.enterprise_resource_id)||{};row._pendingReplace=true;row.component_status="resource_replaced";
      row.enterprise_resource_id=data.enterprise_resource_id;row.resource_code=selected.resource_code;row.resource_name=selected.resource_name;
      row.specification=data.enterprise_specification||selected.specification;row.unit=selected.unit;row.resource_category=selected.resource_category;
      row.calculation_basis=data.calculation_basis;row.consumption=data.enterprise_quantity??null;
      row.enterprise_direct_amount=data.enterprise_direct_amount??null;row.selected_enterprise_price=selected.selected_price;
    }
  }
  for(const row of rows){
    row._previewAmount=row.lifecycle_status==="removed"?"0.000000":row.calculation_basis==="direct_amount"
      ?(row.enterprise_direct_amount===null?null:formatScaled(scaledInteger(row.enterprise_direct_amount,6),6))
      :row.calculation_basis==="quantity_unit_price"?decimalMultiply(row.consumption,row.selected_enterprise_price):row.enterprise_component_amount;
  }
  return rows;
}

function previewSummary(rows){
  const category={labor:[],material:[],machine:[],other:[]};
  for(const row of rows){const bucket=category[row.resource_category]||category.other;if(row._previewAmount===null)return null;bucket.push(row._previewAmount);}
  const labor=decimalAdd(category.labor),material=decimalAdd(category.material),machine=decimalAdd(category.machine),other=decimalAdd(category.other);
  const base=decimalAdd([labor,material,machine,other,state.detail.reference.management_fee||"0"]);
  return {labor,material,machine,other,base,difference:decimalSubtract(base,state.detail.reference.total_fee)};
}

function validationMessage(field,value){
  if(field==="enterprise_specification"){
    if(String(value??"").length>2000)return "规格说明不得超过 2000 个字符。";
    if([...String(value??"")].some(character=>character.charCodeAt(0)<32&&!"\t\r\n".includes(character)))return "规格说明包含不允许的控制字符。";
    return "";
  }
  const scale=field==="enterprise_quantity"?8:6;const text=String(value??"").trim();
  if(!/^\d+(?:\.\d+)?$/.test(text))return "请输入非负十进制数值，不使用科学计数法。";
  if((text.split(".")[1]||"").length>scale)return `最多允许 ${scale} 位小数。`;
  if(text.replace(".","").length>20)return "总精度不得超过 20 位。";
  return "";
}

function cellMarkup(row,field,value,editable){
  const key=`${row._identity}:${field}`;const error=state.validationErrors.get(key);const change=bufferChange(row._identity,field);
  const isEditable=editable&&state.mode==="edit"&&!row._pendingRemove;const classes=["eq-cell",isEditable?"editable":"readonly"];
  if(state.activeCell===key)classes.push("focused");if(change)classes.push("dirty");if(error)classes.push("invalid");
  if(change?.validation_status==="conflicted")classes.push("conflicted");if(state.saving&&change)classes.push("saving");if(state.savedKeys.has(key))classes.push("saved");
  const status=error?"无效":change?.validation_status==="conflicted"?"冲突":state.saving&&change?"保存中":change?"未保存":state.savedKeys.has(key)?"已保存":isEditable?"可编辑":"只读";
  const tooltip=`${fieldText(field)} · ${status}${error?` · ${error}`:""}`;
  return `<td class="${classes.join(" ")}" ${isEditable?`tabindex="0" role="gridcell" data-editable-cell data-component="${row._identity}" data-field="${field}"`:"aria-readonly=\"true\""} title="${esc(tooltip)}"><span class="eq-cell-value">${esc(fmt(value))}</span><small class="eq-cell-state">${esc(status)}</small>${error?`<span class="eq-cell-error" role="alert">${esc(error)}</span>`:""}</td>`;
}

function rowActions(row){
  if(state.mode!=="edit")return "只读";
  if(row._clientAdded)return `<button data-row-action="discard_add">撤销新增</button>`;
  if(row._pendingRemove)return `<button data-row-action="undo_remove">撤销移除</button>`;
  const actions=[`<button data-row-action="replace">替换资源</button>`,`<button data-row-action="remove">移除资源</button>`];
  if(row.component_status!=="inherited"||row._changed)actions.push(`<button data-row-action="restore">恢复 Reference</button>`);
  return actions.join("");
}

function compositionTable(){
  const rows=projectedComponents();const preview=state.buffer?.dirty?previewSummary(rows):null;
  const previewHtml=preview?`<div class="eq-preview-banner" aria-label="未保存预览"><div><span>状态</span><strong>未保存预览</strong></div><div><span>人工 / 材料 / 机具</span><strong>${esc(preview.labor)} / ${esc(preview.material)} / ${esc(preview.machine)}</strong></div><div><span>其他合计</span><strong>${esc(preview.other)}</strong></div><div><span>企业定额基价预览</span><strong>${esc(preview.base)}</strong></div><div><span>总差额预览</span><strong>${esc(preview.difference)}</strong></div></div>`:"";
  const body=rows.map(row=>{
    const quantityEditable=row.calculation_basis==="quantity_unit_price";const directEditable=row.calculation_basis==="direct_amount";
    const rowClass=[row._pendingRemove?"eq-component-pending-remove":"",row._clientAdded?"eq-component-added":"",row._pendingReplace?"eq-component-replaced":""].join(" ");
    return `<tr class="${rowClass}" data-component-row="${row._identity}">
      <td>${esc(row.resource_code)}</td><td>${esc(row.resource_name)}</td><td>${esc(row.resource_category)}</td><td>${esc(statusText(row.calculation_basis))}</td><td>${esc(row.unit)}</td>
      ${cellMarkup(row,"enterprise_specification",row.specification,true)}
      <td class="num eq-cell readonly" title="省消耗量只读"><span class="eq-cell-value">${esc(fmt(row.source_consumption))}</span><small class="eq-cell-state">只读</small></td>
      ${cellMarkup(row,"enterprise_quantity",quantityEditable?row.consumption:null,quantityEditable)}
      ${cellMarkup(row,"enterprise_direct_amount",directEditable?row.enterprise_direct_amount:null,directEditable)}
      <td class="num eq-cell readonly"><span class="eq-cell-value">${esc(fmt(row.provincial_unit_price))}</span><small class="eq-cell-state">只读</small></td>
      <td class="num eq-cell readonly"><span class="eq-cell-value">${esc(fmt(row.selected_enterprise_price))}</span><small class="eq-cell-state">价格标签维护</small></td>
      <td class="num eq-cell readonly"><span class="eq-cell-value">${esc(fmt(row.provincial_component_amount))}</span><small class="eq-cell-state">只读</small></td>
      <td class="num eq-cell readonly"><span class="eq-cell-value">${esc(fmt(row._previewAmount))}</span><small class="eq-cell-state">${row._changed?"未保存预览":"权威结果"}</small></td>
      <td><span class="eq-row-status ${row._changed?"pending":""}">${esc(statusText(row.component_status))}</span></td><td class="eq-row-actions">${rowActions(row)}</td>
    </tr>`;
  }).join("");
  const tools=state.mode==="edit"?`<div class="eq-composition-head-actions"><button id="addComponentButton" class="eq-add-component" type="button">增加企业资源</button><button id="priceJumpButton" type="button">前往价格对比</button></div>`:`<div class="eq-composition-head-actions"><button id="priceJumpButton" type="button">查看价格</button></div>`;
  return `${previewHtml}<div class="eq-composition-head"><p>单元格修改先进入 DraftEditBuffer；保存时由后端 Decimal 引擎权威重算。价格不可在本表修改。</p>${tools}</div><div class="eq-table-wrap"><table class="eq-table eq-composition-table" role="grid"><thead><tr>
    <th>资源编码</th><th>资源名称</th><th>资源类别</th><th>计算类型</th><th>单位</th><th>企业规格</th><th>省消耗量</th><th>企业消耗量</th><th>企业直接金额</th><th>省定额单价</th><th>企业采用价</th><th>省定额合价</th><th>企业合价</th><th>组件状态</th><th>操作</th>
  </tr></thead><tbody>${body}</tbody></table></div>`;
}

function resourcesTable(){
  const rows=state.detail.components.map(row=>`<tr><td>${esc(row.resource_code)}</td><td>${esc(row.resource_name)}</td><td class="num">${esc(fmt(row.source_consumption))}</td><td class="num">${esc(fmt(row.consumption))}</td><td class="num">${esc(fmt(row.provincial_unit_price))}</td><td class="num">${esc(fmt(row.provincial_component_amount))}</td><td class="num">${esc(fmt(row.provincial_fallback_price))}</td><td class="num">${esc(fmt(row.enterprise_manual_price))}</td><td class="num">${esc(fmt(row.selected_enterprise_price))}</td><td class="num">${esc(fmt(row.enterprise_component_amount))}</td><td>${esc(statusText(row.price_source_type))}</td><td>${esc(statusText(row.pricing_review_status))}</td></tr>`).join("");
  return `<div class="eq-table-wrap"><table class="eq-table eq-price-table"><thead><tr><th>编码</th><th>资源名称</th><th>省消耗量</th><th>企业消耗量</th><th>省单价</th><th>省合价</th><th>回填价</th><th>人工价</th><th>当前采用价</th><th>企业合价</th><th>价格来源</th><th>核价状态</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function historyDetails(row){
  const history=row.version_history.map(item=>`<tr><td>V${item.version_no}</td><td>${esc(fmt(item.price_value))}</td><td>${esc(statusText(item.price_source_type))}</td><td>${esc(statusText(item.pricing_review_status))}</td><td>${esc(fmt(item.created_at))}</td></tr>`).join("");
  return `<details><summary>版本 ${row.version_history.length}</summary><table class="eq-mini-table"><thead><tr><th>版本</th><th>价格</th><th>来源</th><th>核价</th><th>创建时间</th></tr></thead><tbody>${history}</tbody></table></details>`;
}
function priceActions(row){
  const actions=[];if(can("enterprise_price.edit")){
    actions.push(`<button data-price-action="manual" data-resource="${row.enterprise_resource_id}">${row.enterprise_manual_price===null?"录入企业价":"调整企业价"}</button>`);
    if(row.price_source_type==="provincial_reference_fallback"&&row.pricing_review_status!=="reviewed_fallback_accepted")actions.push(`<button data-price-action="accept" data-resource="${row.enterprise_resource_id}">接受省定额</button>`);
    if(row.provincial_fallback_price!==null&&row.price_source_type!=="provincial_reference_fallback")actions.push(`<button data-price-action="restore" data-resource="${row.enterprise_resource_id}">恢复省定额</button>`);
  }
  if(can("enterprise_price.review")&&row.selected_price_version_id){actions.push(`<button data-price-action="review" data-resource="${row.enterprise_resource_id}">审核</button>`);actions.push(`<button data-price-action="return" data-resource="${row.enterprise_resource_id}">退回修改</button>`);}
  return actions.join("");
}
function manualPricingTable(){
  const rows=state.priceItems.map(row=>`<tr data-resource-row="${row.enterprise_resource_id}"><td>${esc(row.resource_code)}</td><td>${esc(row.resource_name)}</td><td>${esc(fmt(row.specification))}</td><td>${esc(row.unit)}</td><td class="num">${esc(fmt(row.provincial_reference_price))}</td><td class="num">${esc(fmt(row.provincial_fallback_price))}</td><td class="num">${esc(fmt(row.enterprise_manual_price))}</td><td class="num">${esc(fmt(row.selected_price))}</td><td>${esc(statusText(row.price_source_type))}</td><td>${esc(statusText(row.pricing_review_status))}</td><td>${esc(fmt(row.effective_from))}</td><td>${esc(fmt(row.tax_mode))}</td><td>${esc(fmt(row.region))}</td><td>${esc(fmt(row.adjustment_reason))}</td><td>—</td><td>${historyDetails(row)}</td><td class="eq-row-actions">${priceActions(row)}</td></tr>`).join("");
  return `<div class="eq-price-result"><p>当前筛选 ${esc(state.priceFilter)} · ${state.priceItems.length} 条；企业价格通过受控表单维护。</p><div class="eq-table-wrap"><table class="eq-table eq-price-table"><thead><tr><th>编码</th><th>资源名称</th><th>规格</th><th>单位</th><th>省定额价</th><th>省定额回填价</th><th>企业人工调整价</th><th>当前采用价</th><th>价格来源</th><th>核价状态</th><th>生效日期</th><th>税口径</th><th>区域</th><th>调整原因</th><th>内部价格表历史观察值</th><th>版本历史</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function renderTab(){
  const d=state.detail;if(!d)return;document.querySelectorAll("#tabs button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.activeTab));
  let html="";
  if(state.activeTab==="composition")html=compositionTable();
  if(state.activeTab==="prices")html=resourcesTable();
  if(state.activeTab==="manualPricing")html=manualPricingTable();
  if(state.activeTab==="summary"){
    const s=d.cost_summary;const items=[["人工合计",s.labor_total],["材料合计",s.material_total],["机具合计",s.machine_total],["其他合计",s.other_total],["管理费",s.management_fee],["企业定额基价",s.enterprise_base_price],["省定额基价",s.provincial_base_price],["价格变化贡献",s.price_variance],["消耗量变化贡献",s.consumption_variance],["资源结构变化贡献",s.structure_variance],["费率变化贡献",s.rate_variance],["总差额",s.total_variance],["计算状态",s.calculation_status]];
    html=`<div class="eq-summary-grid">${items.map(([a,b])=>`<div class="eq-summary-card"><span>${esc(a)}</span><strong>${esc(fmt(b))}</strong></div>`).join("")}</div>`;
  }
  if(state.activeTab==="work")html=`<div class="eq-editor"><label>工作内容<textarea disabled>${esc(d.version.work_content)}</textarea></label><label>企业说明<textarea disabled>${esc(d.version.enterprise_note)}</textarea></label></div>`;
  if(state.activeTab==="quantity"||state.activeTab==="conversion"){
    const wanted=state.activeTab==="conversion"?row=>row.rule_type.includes("conversion"):row=>!row.rule_type.includes("conversion");const rows=d.rules.filter(wanted);
    html=rows.length?`<table class="eq-table"><thead><tr><th>类型</th><th>序号</th><th>规则</th><th>企业理由</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(row.rule_type)}</td><td>${row.ordinal}</td><td>${esc(row.rule_text)}</td><td>${esc(fmt(row.enterprise_reason))}</td></tr>`).join("")}</tbody></table>`:`<p class="eq-empty">当前版本没有${state.activeTab==="conversion"?"企业换算":"工程量"}规则。</p>`;
  }
  if(state.activeTab==="changes"){
    const sets=d.change_sets.length?`<table class="eq-table"><thead><tr><th>#</th><th>变更类型</th><th>理由</th><th>时间</th><th>状态</th></tr></thead><tbody>${d.change_sets.map(row=>`<tr><td>${row.change_set_no}</td><td>${esc(row.change_type)}</td><td>${esc(row.change_reason)}</td><td>${esc(row.changed_at)}</td><td>${esc(row.status)}</td></tr>`).join("")}</tbody></table>`:`<p class="eq-empty">暂无 Change Set。</p>`;
    const details=d.component_changes.length?`<h3>组件字段变更</h3><table class="eq-table"><thead><tr><th>类型</th><th>字段</th><th>原因</th><th>修改人</th><th>时间</th><th>审核状态</th></tr></thead><tbody>${d.component_changes.map(row=>`<tr><td>${esc(statusText(row.change_type))}</td><td>${esc(row.field_name)}</td><td>${esc(row.change_reason)}</td><td>${esc(row.changed_by)}</td><td>${esc(row.changed_at)}</td><td>${esc(row.review_status)}</td></tr>`).join("")}</tbody></table>`:`<p class="eq-empty">暂无组件字段变更。</p>`;html=sets+details;
  }
  if(state.activeTab==="pdf")html=`<iframe class="eq-pdf" title="省定额 PDF" src="/api/v1/review/quotas/${esc(d.reference.reference_quota_item_id)}/pdf"></iframe>`;
  if(state.activeTab==="audit")html=d.review_events.length?`<table class="eq-table"><thead><tr><th>从</th><th>到</th><th>意见</th><th>时间</th></tr></thead><tbody>${d.review_events.map(row=>`<tr><td>${esc(fmt(row.from_state))}</td><td>${esc(row.to_state)}</td><td>${esc(fmt(row.comment))}</td><td>${esc(row.created_at)}</td></tr>`).join("")}</tbody></table>`:`<p class="eq-empty">当前 Draft 尚无审核事件。</p>`;
  if(state.activeTab==="history")html=`<table class="eq-table"><thead><tr><th>版本</th><th>状态</th><th>理由</th><th>行版本</th><th></th></tr></thead><tbody>${d.version_history.map(row=>`<tr><td>V${row.version_no}</td><td>${esc(row.status)}</td><td>${esc(row.change_reason)}</td><td>${row.row_version}</td><td><button class="history-open" data-version="${row.enterprise_quota_version_id}">查看</button></td></tr>`).join("")}</tbody></table>`;
  $("tabContent").innerHTML=html;bindTabEvents();
}

function bindTabEvents(){
  document.querySelectorAll(".history-open").forEach(button=>button.addEventListener("click",()=>guardNavigation(()=>loadDetail(button.dataset.version))));
  document.querySelectorAll("[data-price-action]").forEach(button=>button.addEventListener("click",()=>openPriceAction(button)));
  document.querySelectorAll("[data-editable-cell]").forEach(cell=>{
    cell.addEventListener("click",()=>focusCell(cell));cell.addEventListener("dblclick",()=>beginCellEdit(cell));cell.addEventListener("keydown",event=>cellKeydown(event,cell));
  });
  document.querySelectorAll("[data-row-action]").forEach(button=>button.addEventListener("click",()=>rowAction(button)));
  $("addComponentButton")?.addEventListener("click",openAddDrawer);
  $("priceJumpButton")?.addEventListener("click",()=>{state.activeTab="prices";renderTab();});
}

function renderDetail(){
  const d=state.detail;$("quotaCode").textContent=`${d.version.source_quota_code} · ${d.quota.enterprise_quota_code}`;$("quotaName").value=d.quota.quota_name;$("quotaUnit").value=d.version.unit;$("quotaName").disabled=true;$("quotaUnit").disabled=true;$("versionBadge").textContent=`V${d.version.enterprise_quota_version_no} · ${d.version.status}`;
  const editable=d.version.status==="draft"&&can("enterprise_quota.edit");$("editButton").hidden=!editable||state.mode==="edit";$("submitButton").hidden=!can("enterprise_quota.edit")||state.mode==="edit";$("submitButton").disabled=!editable;$("editToolbar").hidden=state.mode!=="edit";updateToolbar();renderTree();renderMeta();renderTab();
}

function updateToolbar(){
  const count=state.buffer?.size||0;$("changeCount").textContent=String(count);$("unsavedCount").textContent=`未保存 ${count} 项`;
  $("saveButton").disabled=count===0||state.saving;$("undoButton").disabled=!state.buffer?.history.length;$("changesButton").disabled=count===0;$("saveNewButton").disabled=count===0||!can("enterprise_quota.create");$("discardAllButton").disabled=count===0;
}

function focusCell(cell){
  document.querySelectorAll(".eq-cell.focused").forEach(node=>node.classList.remove("focused"));state.activeCell=`${cell.dataset.component}:${cell.dataset.field}`;cell.classList.add("focused");cell.focus();
}
function beginCellEdit(cell){
  if(state.mode!=="edit"||cell.querySelector("input"))return;focusCell(cell);state.editingCell=state.activeCell;
  const current=cell.querySelector(".eq-cell-value")?.textContent||"";cell.classList.add("editing");
  cell.innerHTML=`<input class="eq-cell-input" aria-label="编辑${esc(fieldText(cell.dataset.field))}" value="${esc(current==="—"?"":current)}"><small class="eq-cell-state">编辑中 · Enter 确认 · Esc 取消</small>`;
  const input=cell.querySelector("input");input.focus();input.select();
}
function editableCells(field=null){return [...document.querySelectorAll("[data-editable-cell]")].filter(cell=>!field||cell.dataset.field===field);}
function moveCell(cell,direction,sameColumn=false){
  const cells=editableCells(sameColumn?cell.dataset.field:null),index=cells.findIndex(item=>item.dataset.component===cell.dataset.component&&item.dataset.field===cell.dataset.field);if(index<0)return;
  const target=cells[index+direction];if(target){focusCell(target);target.scrollIntoView({block:"nearest",inline:"nearest"});}
}
function commitCell(cell,move=null){
  const input=cell.querySelector("input");if(!input)return true;const value=input.value.trim(),field=cell.dataset.field,key=`${cell.dataset.component}:${field}`;
  const error=validationMessage(field,value);state.editingCell=null;
  if(error){state.validationErrors.set(key,error);renderTab();setTimeout(()=>{const target=document.querySelector(`[data-component="${CSS.escape(cell.dataset.component)}"][data-field="${field}"]`);if(target){focusCell(target);}},0);return false;}
  state.validationErrors.delete(key);const row=projectedComponents().find(item=>item._identity===cell.dataset.component);const base=baseRow(cell.dataset.component);
  const before=field==="enterprise_quantity"?base?.consumption:field==="enterprise_direct_amount"?base?.enterprise_direct_amount:base?.specification;
  const changeType=field==="enterprise_quantity"?"quantity_modified":field==="enterprise_direct_amount"?"amount_modified":"specification_modified";
  state.buffer.put({component_id:row._clientAdded?null:cell.dataset.component,client_component_id:row._clientAdded?cell.dataset.component:null,field_name:field,before_value:before,after_value:value,change_type:changeType,reason:"Excel式单元格编辑"});
  state.savedKeys.clear();renderDetail();setTimeout(()=>{const source=document.querySelector(`[data-component="${CSS.escape(cell.dataset.component)}"][data-field="${field}"]`);if(source){focusCell(source);if(move)moveCell(source,move.direction,move.sameColumn);}},0);return true;
}
function cellKeydown(event,cell){
  const editing=Boolean(cell.querySelector("input"));
  if(event.key==="F2"&&!editing){event.preventDefault();beginCellEdit(cell);return;}
  if(event.key==="Escape"){
    event.preventDefault();if(editing){state.editingCell=null;renderTab();return;}
    const key=`${cell.dataset.component}:${cell.dataset.field}`;if(state.buffer.changes.has(key)){state.buffer.revert(key);renderDetail();}return;
  }
  if(event.key==="Enter"){
    event.preventDefault();if(editing)commitCell(cell,{direction:1,sameColumn:true});else beginCellEdit(cell);return;
  }
  if(event.key==="Tab"){
    event.preventDefault();if(editing)commitCell(cell,{direction:event.shiftKey?-1:1,sameColumn:false});else moveCell(cell,event.shiftKey?-1:1,false);
  }
}

function enterEditMode(){state.mode="edit";state.buffer=new DraftEditBuffer(state.detail.version.enterprise_quota_version_id,state.detail.version.row_version);state.validationErrors.clear();state.savedKeys.clear();state.activeTab="composition";renderDetail();}
function undoLast(){if(state.buffer?.undo()){state.validationErrors.clear();renderDetail();toast("已撤销最近一次前端修改");}}
function discardAll(){state.buffer?.clear();state.validationErrors.clear();renderDetail();toast("已撤销本次编辑会话的全部修改");}

function openModal(title,body,actions=[],wide=false){
  $("modalTitle").textContent=title;$("modalBody").innerHTML=body;$("modalActions").innerHTML="";$("businessModal").classList.toggle("wide",wide);
  for(const action of actions){const button=document.createElement("button");button.type="button";button.textContent=action.label;if(action.kind)button.className=action.kind;button.addEventListener("click",action.handler);$("modalActions").append(button);}
  $("modalBackdrop").hidden=false;$("businessModal").classList.add("open");$("businessModal").setAttribute("aria-hidden","false");
  setTimeout(()=>$("modalBody").querySelector("input,textarea,button")?.focus(),0);
}
function closeModal(){$("modalBackdrop").hidden=true;$("businessModal").classList.remove("open","wide");$("businessModal").setAttribute("aria-hidden","true");}
function openReasonModal(title,message,onApply,kind="primary"){
  openModal(title,`<div class="eq-form"><p>${esc(message)}</p><label>操作原因<textarea id="actionReason" maxlength="2000" required></textarea><span id="actionReasonError" class="eq-inline-error"></span></label></div>`,[
    {label:"取消",handler:closeModal},{label:"加入未保存修改",kind,handler:()=>{const reason=$("actionReason").value.trim();if(!reason){$("actionReasonError").textContent="操作原因必填。";return;}closeModal();onApply(reason);}},
  ]);
}

function rowAction(button){
  const row=projectedComponents().find(item=>item._identity===button.closest("tr").dataset.componentRow);const action=button.dataset.rowAction;
  if(action==="discard_add"){const entry=state.buffer.entries().find(item=>item.client_component_id===row._identity&&item.change_type==="resource_added");if(entry)state.buffer.revert(state.buffer.key(entry));renderDetail();return;}
  if(action==="undo_remove"){const entry=state.buffer.entries().find(item=>item.component_id===row._identity&&item.change_type==="resource_removed");if(entry)state.buffer.revert(state.buffer.key(entry));renderDetail();return;}
  if(action==="replace"){openReplaceDrawer(row);return;}
  if(action==="remove")openReasonModal("移除企业资源","该行将标记为待移除，保存时执行 soft remove；历史组件不会被物理删除。",reason=>{state.buffer.put({component_id:row._identity,field_name:"lifecycle_status",before_value:row.lifecycle_status,after_value:"removed",change_type:"resource_removed",reason});renderDetail();},"danger");
  if(action==="restore")openReasonModal("恢复 Reference","将恢复资源、计算类型、消耗量/直接金额、规格和价格引用。保存前仍可撤销。",reason=>{state.buffer.put({component_id:row._identity,field_name:"component",before_value:{resource:row.enterprise_resource_id,status:row.component_status},after_value:{restore_reference:true},change_type:"restored",reason});renderDetail();});
}

function openDrawer(title,body,actions=[]){
  $("drawerTitle").textContent=title;$("drawerBody").innerHTML=body;$("drawerActions").innerHTML="";
  for(const action of actions){const button=document.createElement("button");button.type="button";button.textContent=action.label;if(action.kind)button.className=action.kind;button.addEventListener("click",action.handler);$("drawerActions").append(button);}
  $("drawerBackdrop").hidden=false;$("resourceDrawer").classList.add("open");$("resourceDrawer").setAttribute("aria-hidden","false");
}
function closeDrawer(){state.drawerMode=null;state.drawerRow=null;$("drawerBackdrop").hidden=true;$("resourceDrawer").classList.remove("open");$("resourceDrawer").setAttribute("aria-hidden","true");}
function resourceOptions(items,selected=""){return items.map(item=>`<option value="${item.enterprise_resource_id}" ${item.enterprise_resource_id===selected?"selected":""}>${esc(item.resource_code)} · ${esc(item.resource_name)} · ${esc(item.unit)}</option>`).join("");}
function drawerForm(mode,row=null){
  const current=row?`<div class="eq-comparison"><div><span>当前资源</span><strong>${esc(row.resource_code)} · ${esc(row.resource_name)}</strong></div><div><span>原消耗量 / 金额</span><strong>${esc(fmt(row.consumption))} / ${esc(fmt(row._previewAmount))}</strong></div></div>`:"";
  return `<div class="eq-form">${current}<label>企业资源搜索<input id="drawerSearch" type="search" placeholder="编码、名称或规格"></label><label>目标企业资源<select id="drawerResource">${resourceOptions(state.priceItems)}</select></label><div class="eq-form-grid"><label>资源编码<input id="drawerCode" readonly></label><label>名称<input id="drawerName" readonly></label><label>规格<input id="drawerMasterSpec" readonly></label><label>单位<input id="drawerUnit" readonly></label></div><label>企业规格<input id="drawerSpecification" maxlength="2000"></label><label>计算类型<select id="drawerBasis"><option value="quantity_unit_price">quantity_unit_price</option><option value="direct_amount">direct_amount</option></select></label><label id="drawerQuantityWrap">企业消耗量<input id="drawerQuantity" inputmode="decimal" value="${esc(row?.consumption??"")}"><span class="eq-field-help">最多 8 位小数，不得为负。</span></label><label id="drawerAmountWrap" hidden>企业直接金额<input id="drawerDirectAmount" inputmode="decimal" value="${esc(row?.enterprise_direct_amount??"")}"><span class="eq-field-help">最多 6 位小数，不得为负。</span></label><div class="eq-form-grid"><label>采用价格预览<input id="drawerPrice" readonly></label><label>预计合价<input id="drawerPreviewAmount" readonly></label></div><div id="drawerUnitWarning"></div><label>操作原因<textarea id="drawerReason" maxlength="2000" required></textarea><span id="drawerError" class="eq-inline-error"></span></label></div>`;
}
function bindResourceDrawer(mode,row=null){
  const update=()=>{
    const selected=resource($("drawerResource").value);if(!selected)return;$("drawerCode").value=selected.resource_code;$("drawerName").value=selected.resource_name;$("drawerMasterSpec").value=selected.specification||"";$("drawerUnit").value=selected.unit;$("drawerSpecification").value=$("drawerSpecification").value||selected.specification||"";
    if(!$("drawerBasis").dataset.touched)$("drawerBasis").value=selected.resource_code==="00010010"?"direct_amount":(row?.calculation_basis||"quantity_unit_price");
    const direct=$("drawerBasis").value==="direct_amount";$("drawerQuantityWrap").hidden=direct;$("drawerAmountWrap").hidden=!direct;$("drawerPrice").value=direct?"不适用":fmt(selected.selected_price);
    $("drawerPreviewAmount").value=direct?fmt($("drawerDirectAmount").value):fmt(decimalMultiply($("drawerQuantity").value,selected.selected_price));
    if(mode==="replace"&&row.unit!==selected.unit)$("drawerUnitWarning").innerHTML=`<div class="eq-unit-warning">单位不一致：${esc(row.unit)} → ${esc(selected.unit)}。不得静默换算。<label><input id="drawerUnitConfirmed" type="checkbox"> 我已人工确认单位差异和新消耗量</label></div>`;else $("drawerUnitWarning").innerHTML="";
  };
  $("drawerSearch").addEventListener("input",()=>{const query=$("drawerSearch").value.trim().toLowerCase();const items=state.priceItems.filter(item=>!query||`${item.resource_code} ${item.resource_name} ${item.specification||""}`.toLowerCase().includes(query));$("drawerResource").innerHTML=resourceOptions(items);update();});
  $("drawerResource").addEventListener("change",()=>{$("drawerSpecification").value="";delete $("drawerBasis").dataset.touched;update();});
  $("drawerBasis").addEventListener("change",()=>{$("drawerBasis").dataset.touched="true";update();});$("drawerQuantity").addEventListener("input",update);$("drawerDirectAmount").addEventListener("input",update);update();
}
function saveDrawer(mode,row=null){
  const selected=resource($("drawerResource").value),basis=$("drawerBasis").value,reason=$("drawerReason").value.trim();
  const value=basis==="direct_amount"?$("drawerDirectAmount").value.trim():$("drawerQuantity").value.trim();const field=basis==="direct_amount"?"enterprise_direct_amount":"enterprise_quantity";
  const error=!selected?"请选择企业资源。":!reason?"操作原因必填。":validationMessage(field,value)||validationMessage("enterprise_specification",$("drawerSpecification").value);
  if(error){$("drawerError").textContent=error;return;}
  if(mode==="replace"&&row.unit!==selected.unit&&!$("drawerUnitConfirmed")?.checked){$("drawerError").textContent="单位不一致时必须人工确认。";return;}
  const after={enterprise_resource_id:selected.enterprise_resource_id,calculation_basis:basis,enterprise_specification:$("drawerSpecification").value.trim(),unit_mismatch_confirmed:Boolean($("drawerUnitConfirmed")?.checked)};
  if(basis==="direct_amount")after.enterprise_direct_amount=value;else after.enterprise_quantity=value;
  if(mode==="add"){
    const clientId=`local-${crypto.randomUUID()}`;state.buffer.put({client_component_id:clientId,field_name:"component",before_value:null,after_value:after,change_type:"resource_added",reason});
  }else state.buffer.put({component_id:row._identity,field_name:"component",before_value:{enterprise_resource_id:row.enterprise_resource_id,unit:row.unit,consumption:row.consumption,amount:row._previewAmount},after_value:after,change_type:"resource_replaced",reason});
  closeDrawer();renderDetail();toast(mode==="add"?"新增资源已加入 DraftEditBuffer":"替换资源已加入 DraftEditBuffer");
}
function openAddDrawer(){state.drawerMode="add";openDrawer("增加企业资源",drawerForm("add"),[{label:"取消",handler:closeDrawer},{label:"加入 DraftEditBuffer",kind:"primary",handler:()=>saveDrawer("add")}]);bindResourceDrawer("add");}
function openReplaceDrawer(row){state.drawerMode="replace";state.drawerRow=row;openDrawer("替换企业资源",drawerForm("replace",row),[{label:"取消",handler:closeDrawer},{label:"加入 DraftEditBuffer",kind:"primary",handler:()=>saveDrawer("replace",row)}]);bindResourceDrawer("replace",row);}

function changeAmountImpact(change){
  const row=projectedComponents().find(item=>item._identity===(change.component_id||change.client_component_id));
  if(change.change_type==="quantity_modified")return decimalMultiply(decimalSubtract(change.after_value,change.before_value,8),row?.selected_enterprise_price);
  if(change.change_type==="amount_modified")return decimalSubtract(change.after_value,change.before_value);
  if(change.change_type==="resource_removed")return decimalSubtract("0",baseRow(change.component_id)?.enterprise_component_amount||"0");
  if(change.change_type==="resource_added")return row?row._previewAmount:null;
  if(change.change_type==="resource_replaced")return decimalSubtract(row?._previewAmount,baseRow(change.component_id)?.enterprise_component_amount);
  return "—";
}
function openChangeSummary(){
  const rows=state.buffer.entries().map(change=>{const row=projectedComponents().find(item=>item._identity===(change.component_id||change.client_component_id))||baseRow(change.component_id)||{};const difference=["quantity_modified","amount_modified"].includes(change.change_type)?decimalSubtract(change.after_value,change.before_value,change.change_type==="quantity_modified"?8:6):"结构/文本";return `<tr data-summary-key="${esc(state.buffer.key(change))}"><td>${esc(row.resource_code)}</td><td>${esc(row.resource_name)}</td><td>${esc(fieldText(change.field_name))}</td><td>${esc(fmt(typeof change.before_value==="object"?JSON.stringify(change.before_value):change.before_value))}</td><td>${esc(fmt(typeof change.after_value==="object"?JSON.stringify(change.after_value):change.after_value))}</td><td>${esc(fmt(difference))}</td><td>${esc(fmt(changeAmountImpact(change)))}</td><td><input data-change-reason value="${esc(change.reason)}" maxlength="2000"></td><td><button data-jump-change>定位</button></td></tr>`;}).join("");
  openModal(`查看变更（${state.buffer.size}）`,`<div class="eq-table-wrap"><table class="eq-change-table"><thead><tr><th>资源编码</th><th>资源名称</th><th>字段</th><th>修改前</th><th>修改后</th><th>差异</th><th>金额影响</th><th>修改原因</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`,[{label:"返回编辑",kind:"primary",handler:closeModal}],true);
  document.querySelectorAll("[data-change-reason]").forEach(input=>input.addEventListener("change",()=>{const key=input.closest("tr").dataset.summaryKey;const change=state.buffer.changes.get(key);if(change)change.reason=input.value.trim()||change.reason;}));
  document.querySelectorAll("[data-jump-change]").forEach(button=>button.addEventListener("click",()=>{const key=button.closest("tr").dataset.summaryKey,change=state.buffer.changes.get(key);closeModal();state.activeTab="composition";renderTab();setTimeout(()=>{const row=document.querySelector(`[data-component-row="${CSS.escape(change.component_id||change.client_component_id)}"]`);row?.scrollIntoView({block:"center"});const cell=row?.querySelector(`[data-field="${change.field_name}"]`);if(cell)focusCell(cell);},0);}));
}

function mapServerErrors(error){
  const detail=error.payload?.detail;for(const item of detail?.field_errors||[]){const component=item.component_id;const field=item.field_name==="consumption"?"enterprise_quantity":item.field_name==="specification_override"?"enterprise_specification":item.field_name;state.validationErrors.set(`${component}:${field}`,item.message);}
}
function openSaveDialog(saveAsNew=false){
  if(!state.buffer?.dirty){toast("当前没有未保存修改");return;}
  openModal(saveAsNew?"另存为新版本":"保存 Draft 修改",`<div class="eq-form"><p>将以单事务保存 ${state.buffer.size} 项修改；任一字段失败时全部回滚。</p><label>本批次保存原因<textarea id="batchReason" maxlength="2000" required></textarea><span id="batchReasonError" class="eq-inline-error"></span></label></div>`,[{label:"取消",handler:closeModal},{label:saveAsNew?"创建新版本":"批量保存",kind:"primary",handler:async()=>{const reason=$("batchReason").value.trim();if(!reason){$("batchReasonError").textContent="保存原因必填。";return;}closeModal();await saveBuffer(reason,saveAsNew);}}]);
}
async function saveBuffer(reason,saveAsNew=false,showResult=true){
  if([...state.validationErrors.values()].some(Boolean)){toast("请先修正单元格错误",true);return false;}
  state.saving=true;renderDetail();const versionId=state.buffer.quota_version_id;const savedKeys=new Set(state.buffer.entries().map(change=>state.buffer.key(change)));
  try{
    const result=await api(`/api/v1/enterprise-quota/versions/${versionId}/components/batch`,{method:"PATCH",body:JSON.stringify({base_row_version:state.buffer.base_row_version,changes:state.buffer.payload(),change_reason:reason,idempotency_key:`spreadsheet-${crypto.randomUUID()}`,save_as_new:saveAsNew})});
    state.detail=result.detail;state.savedKeys=savedKeys;state.buffer=new DraftEditBuffer(result.enterprise_quota_version_id,result.row_version);state.serverConflictDetail=null;state.validationErrors.clear();state.savedMessage=`已通过单事务保存 ${result.saved_change_count} 项修改${saveAsNew?"，并创建新 Draft 版本":""}。`;
    renderDetail();if(showResult)openModal("保存完成",`<div class="eq-saved-banner">${esc(state.savedMessage)}</div><p>服务器已使用 Decimal 权威重算，并返回最新 row_version：${esc(result.row_version)}。</p>`,[{label:"继续编辑",kind:"primary",handler:closeModal},{label:"退出编辑",handler:()=>{closeModal();leaveEditMode();}}]);return true;
  }catch(error){
    if(error.status===409){await showConflict(error);return false;}
    if(error.status===422){mapServerErrors(error);renderDetail();toast("服务器返回字段级校验错误",true);return false;}
    toast(error.message,true);return false;
  }finally{state.saving=false;updateToolbar();}
}
async function showConflict(error){
  for(const change of state.buffer.changes.values())change.validation_status="conflicted";
  state.serverConflictDetail=await api(`/api/v1/enterprise-quota/versions/${state.buffer.quota_version_id}`);renderDetail();
  const current=error.payload?.detail?.current_row_version||state.serverConflictDetail.version.row_version;
  openModal("当前版本已被其他用户修改",`<div class="eq-conflict-options"><div class="eq-conflict-card">当前服务器 row_version 为 ${esc(current)}，你的基线为 ${esc(state.buffer.base_row_version)}。系统没有覆盖服务器数据。</div><p>请选择如何处理本地 DraftEditBuffer。</p></div>`,[
    {label:"查看服务器新值",handler:showServerValues},{label:"保留我的修改",handler:closeModal},
    {label:"重新应用",kind:"primary",handler:()=>{state.detail=state.serverConflictDetail;state.buffer.rebase(state.detail);state.serverConflictDetail=null;closeModal();renderDetail();toast("已基于服务器新值重新应用本地修改");}},
    {label:"放弃我的修改",kind:"danger",handler:()=>{state.detail=state.serverConflictDetail;state.buffer=new DraftEditBuffer(state.detail.version.enterprise_quota_version_id,state.detail.version.row_version);state.serverConflictDetail=null;closeModal();renderDetail();}},
  ]);
}
function showServerValues(){
  const rows=state.buffer.entries().map(change=>{const server=state.serverConflictDetail.components.find(row=>row.enterprise_quota_component_version_id===change.component_id);let value="—";if(server){if(change.field_name==="enterprise_quantity")value=server.consumption;if(change.field_name==="enterprise_direct_amount")value=server.enterprise_direct_amount;if(change.field_name==="enterprise_specification")value=server.specification;}return `<tr><td>${esc(change.component_id||change.client_component_id)}</td><td>${esc(fieldText(change.field_name))}</td><td>${esc(fmt(value))}</td><td>${esc(fmt(typeof change.after_value==="object"?JSON.stringify(change.after_value):change.after_value))}</td></tr>`;}).join("");
  $("modalBody").innerHTML=`<div class="eq-table-wrap"><table class="eq-change-table"><thead><tr><th>组件</th><th>字段</th><th>服务器新值</th><th>我的修改</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function guardNavigation(action){if(state.mode==="edit"&&state.buffer?.dirty){state.pendingNavigation=action;openExitDialog();}else action();}
function openExitDialog(){
  if(!state.buffer?.dirty){leaveEditMode();if(state.pendingNavigation){const action=state.pendingNavigation;state.pendingNavigation=null;action();}return;}
  openModal("存在未保存修改",`<div class="eq-form"><p>当前有 ${state.buffer.size} 项未保存修改。离开定额或切换版本前请选择处理方式。</p><label>保存并退出原因<textarea id="exitSaveReason" maxlength="2000"></textarea><span id="exitReasonError" class="eq-inline-error"></span></label></div>`,[
    {label:"继续编辑",handler:()=>{state.pendingNavigation=null;closeModal();}},
    {label:"放弃修改",kind:"danger",handler:()=>{state.buffer.clear();closeModal();leaveEditMode();const action=state.pendingNavigation;state.pendingNavigation=null;if(action)action();}},
    {label:"保存并退出",kind:"primary",handler:async()=>{const reason=$("exitSaveReason").value.trim();if(!reason){$("exitReasonError").textContent="保存原因必填。";return;}closeModal();if(await saveBuffer(reason,false,false)){leaveEditMode();const action=state.pendingNavigation;state.pendingNavigation=null;if(action)action();}}},
  ]);
}
function leaveEditMode(){state.mode="view";state.buffer=null;state.validationErrors.clear();state.activeCell=null;state.editingCell=null;renderDetail();}

function openPriceAction(button){
  if(state.buffer?.dirty){toast("请先保存或撤销组件修改，再维护价格。",true);return;}
  const row=state.priceItems.find(item=>item.enterprise_resource_id===button.dataset.resource);const action=button.dataset.priceAction;if(!row)return;
  const manual=action==="manual";const body=manual?`<div class="eq-form"><p>${esc(row.resource_code)} · ${esc(row.resource_name)}</p><label>企业资源单价<input id="priceValue" inputmode="decimal" value="${esc(row.selected_price??"")}"></label><label>税口径<input id="priceTax" value="${esc(row.tax_mode||"provincial_basis_unknown")}"></label><label>区域<input id="priceRegion" value="${esc(row.region||"广东省")}"></label><label>调整原因<textarea id="priceReason"></textarea><span id="priceError" class="eq-inline-error"></span></label></div>`:`<div class="eq-form"><p>${esc(row.resource_code)} · ${esc(row.resource_name)}</p><label>${action==="return"?"退回原因":"操作原因"}<textarea id="priceReason"></textarea><span id="priceError" class="eq-inline-error"></span></label></div>`;
  openModal({manual:"录入/调整企业价",accept:"接受省定额回填",restore:"恢复省定额回填",review:"审核企业价格",return:"退回价格修改"}[action],body,[{label:"取消",handler:closeModal},{label:"执行",kind:"primary",handler:()=>executePriceAction(row,action)}]);
}
async function executePriceAction(row,action){
  const reason=$("priceReason").value.trim();if(!reason){$("priceError").textContent="操作原因必填。";return;}
  const base={row_version:row.price_row_version||row.resource_row_version,idempotency_key:`price-${crypto.randomUUID()}`,change_reason:reason};let path,payload=base;
  if(action==="manual"){
    const price=$("priceValue").value.trim(),tax=$("priceTax").value.trim(),region=$("priceRegion").value.trim(),error=validationMessage("enterprise_direct_amount",price);if(error||!tax||!region){$("priceError").textContent=error||"税口径和区域必填。";return;}
    path=`/api/v1/enterprise-quota/prices/resources/${row.enterprise_resource_id}/manual`;payload={...base,price_value:price,tax_mode:tax,region,effective_from:new Date().toISOString()};
  }else if(action==="accept")path=`/api/v1/enterprise-quota/prices/${row.selected_price_version_id}/accept-fallback`;
  else if(action==="restore")path=`/api/v1/enterprise-quota/prices/resources/${row.enterprise_resource_id}/restore-fallback`;
  else{path=`/api/v1/enterprise-quota/prices/${row.selected_price_version_id}/review`;payload={...base,action:action==="return"?"return":"review"};}
  try{await api(path,{method:"POST",body:JSON.stringify(payload)});closeModal();toast("价格操作已保存");await refreshCurrent();}catch(error){$("priceError").textContent=error.message;}
}
function openSubmitReview(){
  openModal("提交审核",`<div class="eq-form"><p>省定额回填不会被视为企业确认价。提交后 Draft 将进入审核状态。</p><label>提交说明<textarea id="submitComment"></textarea><span id="submitError" class="eq-inline-error"></span></label></div>`,[{label:"取消",handler:closeModal},{label:"提交审核",kind:"primary",handler:async()=>{const comment=$("submitComment").value.trim();if(!comment){$("submitError").textContent="提交说明必填。";return;}try{await api(`/api/v1/enterprise-quota/versions/${state.detail.version.enterprise_quota_version_id}/submit`,{method:"POST",body:JSON.stringify({row_version:state.detail.version.row_version,idempotency_key:`submit-${crypto.randomUUID()}`,comment})});closeModal();toast("已提交审核");await refreshCurrent();}catch(error){$("submitError").textContent=error.message;}}}]);
}

async function loadPrices(){const params=new URLSearchParams({filter:state.priceFilter,threshold_percentage:state.priceThreshold});const result=await api(`/api/v1/enterprise-quota/prices?${params}`);state.priceItems=result.items;$("priceCoverage").textContent=`计算覆盖 ${result.calculation_price_coverage} · 企业确认 ${result.enterprise_confirmed_price_coverage}`;}
async function loadDetail(version){state.mode="view";state.buffer=null;state.detail=await api(`/api/v1/enterprise-quota/versions/${version}`);renderDetail();}
async function refreshCurrent(){state.summary=await api("/api/v1/enterprise-quota/summary");state.tree=(await api("/api/v1/enterprise-quota/tree")).items;await loadPrices();renderMetrics();if(state.detail)state.detail=await api(`/api/v1/enterprise-quota/versions/${state.detail.version.enterprise_quota_version_id}`);renderDetail();}
async function init(){try{state.me=await api("/api/v1/auth/me");state.summary=await api("/api/v1/enterprise-quota/summary");state.tree=(await api("/api/v1/enterprise-quota/tree")).items;await loadPrices();renderMetrics();renderTree();if(state.tree.length)await loadDetail(state.tree[0].enterprise_quota_version_id);}catch(error){toast(error.message,true);}}

$("quotaSearch").addEventListener("input",renderTree);
document.querySelectorAll("#tabs button").forEach(button=>button.addEventListener("click",()=>{state.activeTab=button.dataset.tab;renderTab();}));
$("editButton").addEventListener("click",enterEditMode);$("saveButton").addEventListener("click",()=>openSaveDialog(false));$("saveNewButton").addEventListener("click",()=>openSaveDialog(true));
$("undoButton").addEventListener("click",undoLast);$("changesButton").addEventListener("click",openChangeSummary);$("discardAllButton").addEventListener("click",discardAll);$("exitEditButton").addEventListener("click",openExitDialog);$("submitButton").addEventListener("click",openSubmitReview);
$("drawerCloseButton").addEventListener("click",closeDrawer);$("drawerBackdrop").addEventListener("click",closeDrawer);$("modalCloseButton").addEventListener("click",closeModal);
$("priceFilterButton").addEventListener("click",async()=>{state.priceFilter=$("priceFilter").value;state.priceThreshold=$("priceThreshold").value||"20";try{await loadPrices();state.activeTab="manualPricing";renderTab();}catch(error){toast(error.message,true);}});
document.addEventListener("keydown",event=>{
  if(state.mode!=="edit"||!event.target.closest(".eq-center"))return;
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="s"){event.preventDefault();openSaveDialog(false);}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="z"&&!event.target.matches("input,textarea")){event.preventDefault();undoLast();}
});
window.addEventListener("beforeunload",event=>{if(state.buffer?.dirty){event.preventDefault();event.returnValue="";}});
document.querySelectorAll("a").forEach(link=>link.addEventListener("click",event=>{if(state.buffer?.dirty){event.preventDefault();guardNavigation(()=>{location.href=link.href;});}}));

window.__enterpriseQuotaSpreadsheet={state,projectedComponents,previewSummary,openAddDrawer,openReplaceDrawer,openChangeSummary,saveBuffer,showConflict};
init();
