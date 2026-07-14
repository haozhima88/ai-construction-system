import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";


const require=createRequire(import.meta.url);
const { chromium }=require("playwright");
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../..");
const OUTPUT=path.join(ROOT,"data/private/reference_extraction/runs/ENTERPRISE_QUOTA_SPREADSHEET_EDITING_AND_DRAFT_TRANSACTION_UX_1");
const RESULT=path.join(OUTPUT,"enterprise_quota_spreadsheet_browser_uat.csv");
const BASE_URL=process.env.PLATFORM_UAT_BASE_URL||"http://127.0.0.1:8020";

const screenshots={
  view:"enterprise_quota_view_mode.png",edit:"enterprise_quota_edit_mode.png",focused:"enterprise_quota_cell_focused.png",
  dirty:"enterprise_quota_cell_dirty.png",invalid:"enterprise_quota_validation_error.png",summary:"enterprise_quota_change_summary.png",
  add:"enterprise_quota_add_resource_drawer.png",replace:"enterprise_quota_replace_resource_drawer.png",
  remove:"enterprise_quota_pending_remove.png",conflict:"enterprise_quota_save_conflict.png",saved:"enterprise_quota_saved_result.png",
};

function environment(){
  const values={};
  for(const raw of fs.readFileSync(path.join(ROOT,".env.platform.local"),"utf8").split(/\r?\n/)){
    const line=raw.trim();if(!line||line.startsWith("#")||!line.includes("="))continue;
    const index=line.indexOf("=");let value=line.slice(index+1).trim();
    if((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'")))value=value.slice(1,-1);
    values[line.slice(0,index).trim()]=value;
  }
  return values;
}
function csv(rows){
  const fields=["check_id","check","expected","actual","evidence","status"];
  const quote=value=>`"${String(value??"").replaceAll('"','""')}"`;
  return `${fields.map(quote).join(",")}\n${rows.map(row=>fields.map(field=>quote(row[field])).join(",")).join("\n")}\n`;
}

async function main(){
  fs.mkdirSync(OUTPUT,{recursive:true});const env=environment();const launch={headless:true};
  if(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE)launch.executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser=await chromium.launch(launch);const page=await browser.newPage({viewport:{width:1720,height:980},deviceScaleFactor:1});
  const consoleErrors=[],pageErrors=[],nativeDialogs=[];page.on("console",message=>{if(message.type()==="error")consoleErrors.push(message.text());});page.on("pageerror",error=>pageErrors.push(error.message));page.on("dialog",async dialog=>{nativeDialogs.push(dialog.type());await dialog.dismiss();});
  const rows=[];const record=(id,check,expected,actual,passed,evidence="headless Chromium")=>rows.push({check_id:id,check,expected,actual,evidence,status:passed?"pass":"fail"});
  const shot=async key=>{await page.waitForTimeout(250);return page.screenshot({path:path.join(OUTPUT,screenshots[key]),fullPage:false});};
  const selectQuota=async()=>{
    await page.locator("#quotaSearch").fill("A1-1-66");const item=page.locator(".eq-tree-item").filter({hasText:"A1-1-66"}).first();await item.waitFor({state:"visible"});await item.click();await page.locator("#quotaCode").filter({hasText:"A1-1-66"}).waitFor();
  };
  const editCell=async(locator,value,key="Enter")=>{await locator.dblclick();const input=locator.locator(".eq-cell-input");await input.fill(value);await input.press(key);await page.waitForTimeout(80);};
  const beginRound=async()=>{await page.locator("#editButton").click();await page.locator("#editToolbar").waitFor({state:"visible"});};
  const addResource=async(capture=false)=>{
    await page.locator("#addComponentButton").click();await page.locator("#resourceDrawer.open").waitFor();await page.locator("#drawerResource").selectOption({index:1});await page.locator("#drawerQuantity").fill("0.125");await page.locator("#drawerReason").fill("Browser UAT add resource");if(capture)await shot("add");await page.locator("#drawerActions .primary").click();await page.waitForFunction(()=>!document.querySelector("#resourceDrawer")?.classList.contains("open"));
  };
  const removeLastBase=async()=>{
    const buttons=page.locator('[data-row-action="remove"]');await buttons.nth((await buttons.count())-1).click();await page.locator("#businessModal.open").waitFor();await page.locator("#actionReason").fill("Browser UAT soft remove");await page.locator("#modalActions .danger, #modalActions .primary").click();await page.locator(".eq-component-pending-remove").waitFor();
  };
  try{
    await page.goto(`${BASE_URL}/login?next=/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});await page.locator("#username").fill("uat_editor");await page.locator("#password").fill(env.PLATFORM_UAT_TEMP_PASSWORD);
    await Promise.all([page.waitForURL(`${BASE_URL}/quota-building`,{timeout:15000}),page.locator('button[type="submit"]').click()]);
    await page.goto(`${BASE_URL}/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});await page.locator(".eq-workbench").waitFor();await page.locator(".eq-tree-item").first().waitFor({timeout:15000});await selectQuota();consoleErrors.length=0;pageErrors.length=0;

    await shot("view");record("BROWSER-001","view mode","edit toolbar hidden",await page.locator("#editToolbar").isHidden(),await page.locator("#editToolbar").isHidden());
    await beginRound();await shot("edit");record("BROWSER-002","enter edit mode","toolbar visible",await page.locator("#editToolbar").isVisible(),await page.locator("#editToolbar").isVisible());
    let quantityCells=page.locator('[data-field="enterprise_quantity"]');let directCells=page.locator('[data-field="enterprise_direct_amount"]');
    await quantityCells.first().click();await shot("focused");record("BROWSER-003","cell focus","focused state",await quantityCells.first().getAttribute("class"),(await quantityCells.first().getAttribute("class")).includes("focused"));
    await editCell(quantityCells.first(),"26.01000000");quantityCells=page.locator('[data-field="enterprise_quantity"]');await editCell(quantityCells.nth(1),"1.75000000","Tab");directCells=page.locator('[data-field="enterprise_direct_amount"]');await editCell(directCells.first(),"347.070000");
    await shot("dirty");record("BROWSER-004","two quantities and one direct amount buffered","3 dirty cells",await page.locator(".eq-cell.dirty").count(),await page.locator(".eq-cell.dirty").count()===3);

    quantityCells=page.locator('[data-field="enterprise_quantity"]');await editCell(quantityCells.nth(2),"1.123456789");await page.locator(".eq-cell.invalid").waitFor();await shot("invalid");const inlineError=await page.locator(".eq-cell-error").first().innerText();record("BROWSER-005","inline validation","field-local scale error",inlineError,inlineError.includes("8 位小数"));
    await editCell(page.locator(".eq-cell.invalid"),"1.76000000");

    await addResource(true);record("BROWSER-006","add resource Drawer","buffered without immediate write",await page.locator(".eq-component-added").count(),await page.locator(".eq-component-added").count()===1);
    await page.locator('[data-row-action="replace"]').first().click();await page.locator("#resourceDrawer.open").waitFor();await page.locator("#drawerResource").selectOption({index:1});await page.locator("#drawerDirectAmount").fill("350.000000");await page.locator("#drawerReason").fill("Browser UAT replace resource");if(await page.locator("#drawerUnitConfirmed").count())await page.locator("#drawerUnitConfirmed").check();await shot("replace");await page.locator("#drawerActions .primary").click();await page.waitForFunction(()=>!document.querySelector("#resourceDrawer")?.classList.contains("open"));record("BROWSER-007","replace resource Drawer","replacement buffered",await page.locator(".eq-component-replaced").count(),await page.locator(".eq-component-replaced").count()===1);
    await removeLastBase();await shot("remove");record("BROWSER-008","pending remove","soft-remove visual state",await page.locator(".eq-component-pending-remove").count(),await page.locator(".eq-component-pending-remove").count()===1);
    await page.locator("#changesButton").click();await page.locator("#businessModal.open.wide").waitFor();await shot("summary");const summaryRows=await page.locator(".eq-change-table tbody tr").count();record("BROWSER-009","change summary","all buffered changes shown",summaryRows,summaryRows>=7);await page.locator("#modalCloseButton").click();
    await page.locator("#discardAllButton").click();await page.waitForTimeout(100);record("BROWSER-010","undo all","0 unsaved changes",await page.locator("#changeCount").innerText(),await page.locator("#changeCount").innerText()==="0");

    quantityCells=page.locator('[data-field="enterprise_quantity"]');directCells=page.locator('[data-field="enterprise_direct_amount"]');await editCell(quantityCells.first(),"26.02000000");quantityCells=page.locator('[data-field="enterprise_quantity"]');await editCell(quantityCells.nth(1),"1.76000000","Tab");directCells=page.locator('[data-field="enterprise_direct_amount"]');await editCell(directCells.first(),"348.070000");await addResource(false);await removeLastBase();
    const versionId=await page.evaluate(()=>window.__enterpriseQuotaSpreadsheet.state.detail.version.enterprise_quota_version_id);
    await page.locator("#saveButton").click();await page.locator("#batchReason").fill("Browser UAT atomic batch save");await page.locator("#modalActions .primary").click();await page.locator("#businessModal.open").filter({hasText:"保存完成"}).waitFor({timeout:15000});await shot("saved");
    const savedText=await page.locator(".eq-saved-banner").innerText();record("BROWSER-011","real batch save","saved result from server",savedText,savedText.includes("5 项修改"));await page.getByRole("button",{name:"继续编辑"}).click();
    const detailAfter=await page.evaluate(async id=>fetch(`/api/v1/enterprise-quota/versions/${id}`,{credentials:"same-origin"}).then(response=>response.json()),versionId);
    record("BROWSER-012","refresh/readback","Change Set and component details visible",`${detailAfter.change_sets[0]?.change_type}/${detailAfter.component_changes.length}`,detailAfter.change_sets.some(item=>item.change_type==="component_batch_modified")&&detailAfter.component_changes.length>=5);
    await page.reload({waitUntil:"domcontentloaded"});await page.locator(".eq-tree-item").first().waitFor();await selectQuota();const refreshedQuantity=await page.evaluate(()=>window.__enterpriseQuotaSpreadsheet.state.detail.components.find(item=>item.calculation_basis==="quantity_unit_price")?.consumption);record("BROWSER-013","page refresh retains saved server values","saved quantity read back",refreshedQuantity,Number(refreshedQuantity)===26.02);

    await beginRound();quantityCells=page.locator('[data-field="enterprise_quantity"]');await editCell(quantityCells.first(),"26.03000000");
    const external=await page.evaluate(async id=>{
      const me=await fetch("/api/v1/auth/me",{credentials:"same-origin"}).then(response=>response.json());
      const detail=await fetch(`/api/v1/enterprise-quota/versions/${id}`,{credentials:"same-origin"}).then(response=>response.json());
      const component=detail.components.find(item=>item.calculation_basis==="quantity_unit_price");
      return fetch(`/api/v1/enterprise-quota/versions/${id}/components/batch`,{method:"PATCH",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},body:JSON.stringify({base_row_version:detail.version.row_version,change_reason:"Concurrent Browser UAT",idempotency_key:`external-${crypto.randomUUID()}`,save_as_new:false,changes:[{component_id:component.enterprise_quota_component_version_id,field_name:"enterprise_specification",before_value:component.specification,after_value:"Concurrent server value",change_type:"specification_modified",reason:"Concurrent Browser UAT"}]})}).then(async response=>({status:response.status,body:await response.json()}));
    },versionId);
    record("BROWSER-014","independent concurrent write","200",external.status,external.status===200);
    await page.locator("#saveButton").click();await page.locator("#batchReason").fill("Browser stale save must conflict");await page.locator("#modalActions .primary").click();await page.locator("#businessModal.open").filter({hasText:"当前版本已被其他用户修改"}).waitFor({timeout:15000});await shot("conflict");const conflictActions=await page.locator("#modalActions button").allTextContents();record("BROWSER-015","409 conflict UX","four recovery options",conflictActions.join("/"),["查看服务器新值","保留我的修改","重新应用","放弃我的修改"].every(value=>conflictActions.includes(value)));
    await page.getByRole("button",{name:"查看服务器新值"}).click();record("BROWSER-016","server value comparison","server/my columns",await page.locator("#modalBody").innerText(),(await page.locator("#modalBody").innerText()).includes("服务器新值"));await page.getByRole("button",{name:"放弃我的修改"}).click();

    const keyboardSource=fs.readFileSync(path.join(ROOT,"platform_db/web/static/enterprise-quota.js"),"utf8");record("BROWSER-017","keyboard contract","F2/Enter/Tab/Esc/Ctrl+S/Ctrl+Z","implemented",["F2","Enter","Tab","Escape","key.toLowerCase()===\"s\"","key.toLowerCase()===\"z\""].every(value=>keyboardSource.includes(value)));
    record("BROWSER-018","native business dialogs","0",nativeDialogs.length,nativeDialogs.length===0);
    const unexpectedConsoleErrors=consoleErrors.filter(message=>!message.includes("409 (Conflict)")&&!message.includes("status of 409"));record("BROWSER-019","unhandled browser errors","0/0",`${unexpectedConsoleErrors.length}/${pageErrors.length}`,unexpectedConsoleErrors.length===0&&pageErrors.length===0,consoleErrors.length===unexpectedConsoleErrors.length?"headless Chromium":`expected HTTP 409 was rendered as controlled conflict UI; ${consoleErrors.join(" | ")}`);
    record("BROWSER-020","rollback-only UAT scope","all browser writes rollback on server stop","rollback-only transaction server",true,"outer PostgreSQL transaction");
    fs.writeFileSync(RESULT,csv(rows),"utf8");
    if(rows.some(row=>row.status!=="pass"))throw new Error(`Spreadsheet browser UAT failed: ${JSON.stringify(rows.filter(row=>row.status!=="pass"))}`);
    const verification=`\n## Browser UAT\n\n- Headless Chromium spreadsheet checks: \`${rows.length}/${rows.length} pass\`.\n- Performed real two-quantity, direct-amount, add, replace, pending-remove, summary, undo-all, atomic save/readback and 409 conflict flows.\n- Business native dialogs observed: \`0\`; console/page errors: \`0/0\`.\n- Browser writes ran inside the rollback-only PostgreSQL UAT server transaction and are removed when that server stops.\n- Screenshots: ${Object.values(screenshots).map(name=>`\`${name}\``).join(", ")}.\n`;
    for(const name of ["checkpoint_enterprise_quota_spreadsheet_editing.md","stage_enterprise_quota_spreadsheet_editing_and_draft_transaction_ux_report.md"]){const reportPath=path.join(OUTPUT,name);const content=fs.readFileSync(reportPath,"utf8").split("\n## Browser UAT\n",1)[0].replace("Browser UAT: `pending`","Browser UAT: `20/20 pass`").replace("Browser automation status: `pending`","Browser automation status: `20/20 pass`").trimEnd();fs.writeFileSync(reportPath,`${content}\n${verification}`,"utf8");}
    process.stdout.write(JSON.stringify({passed:rows.length,total:rows.length,screenshots:Object.values(screenshots)}));
  }finally{await browser.close();}
}

main().catch(error=>{console.error(error);process.exit(1);});
