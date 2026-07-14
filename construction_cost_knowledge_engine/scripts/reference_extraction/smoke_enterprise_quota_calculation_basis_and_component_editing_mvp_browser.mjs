import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require=createRequire(import.meta.url);
const { chromium }=require("playwright");
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../..");
const OUTPUT=path.join(ROOT,"data/private/reference_extraction/runs/ENTERPRISE_QUOTA_CALCULATION_BASIS_AND_COMPONENT_EDITING_MVP_1");
const RESULT=path.join(OUTPUT,"enterprise_quota_component_web_smoke.csv");
const BASE_URL=process.env.PLATFORM_UAT_BASE_URL||"http://127.0.0.1:8019";

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

async function dismissFirstDialog(page,locator){
  let message="";page.once("dialog",async dialog=>{message=dialog.message();await dialog.dismiss();});
  await locator.click();await page.waitForTimeout(100);return message;
}

async function main(){
  const env=environment();const launchOptions={headless:true};
  if(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE)launchOptions.executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser=await chromium.launch(launchOptions);
  const page=await browser.newPage({viewport:{width:1600,height:960},deviceScaleFactor:1});
  const consoleErrors=[];const pageErrors=[];
  page.on("console",message=>{if(message.type()==="error")consoleErrors.push(message.text());});
  page.on("pageerror",error=>pageErrors.push(error.message));
  const checks=[];
  const record=(id,name,expected,actual,passed)=>checks.push({check_id:id,check:name,expected,actual,verification:"headless Chromium",status:passed?"pass":"fail"});
  try{
    await page.goto(`${BASE_URL}/login?next=/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});
    await page.locator("#username").fill("uat_editor");await page.locator("#password").fill(env.PLATFORM_UAT_TEMP_PASSWORD);
    await Promise.all([page.waitForURL(`${BASE_URL}/quota-building`,{timeout:15000}),page.locator('button[type="submit"]').click()]);
    await page.goto(`${BASE_URL}/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});
    await page.locator(".eq-workbench").waitFor({state:"visible"});
    await page.locator(".eq-tree-item").first().waitFor({state:"visible",timeout:15000});
    await page.locator("#quotaCode").filter({hasText:"A1-1-"}).waitFor({timeout:15000});
    await page.locator('#tabs button[data-tab="composition"].active').waitFor({state:"visible"});
    consoleErrors.length=0;pageErrors.length=0;

    const metrics=(await page.locator("#metrics").innerText()).replaceAll("\n"," | ");
    record("BROWSER-001","component calculation metric","137/137",metrics,metrics.includes("定额可计算")&&metrics.includes("137/137"));
    const treeCount=await page.locator(".eq-tree-item").count();
    record("BROWSER-002","A1.1 quota tree","137",String(treeCount),treeCount===137);
    const activeLabel=await page.locator('#tabs button[data-tab="composition"]').innerText();
    record("BROWSER-003","default tab","定额组成",activeLabel,activeLabel==="定额组成");

    const headers=await page.locator("#tabContent thead").first().innerText();
    const requiredHeaders=["资源编码","资源名称","资源类别","计算类型","单位","省消耗量","企业消耗量","消耗量差异","省定额单价","企业采用价","省定额合价","企业合价","价格/金额来源","组件状态","操作"];
    record("BROWSER-004","composition columns","15 required columns",headers,requiredHeaders.every(value=>headers.includes(value)));
    const componentRows=await page.locator("tr[data-component-row]").count();
    record("BROWSER-005","composition rows","non-empty",String(componentRows),componentRows>0);
    const quantityActions=await page.locator('[data-component-action="edit_quantity"]').count();
    const directActions=await page.locator('[data-component-action="edit_direct_amount"]').count();
    const addActions=await page.locator("#addComponentButton").count();
    record("BROWSER-006","basis-specific editor actions","quantity/direct/add visible",`${quantityActions}/${directActions}/${addActions}`,quantityActions>0&&directActions>0&&addActions===1);

    const quantityDialog=await dismissFirstDialog(page,page.locator('[data-component-action="edit_quantity"]').first());
    const directDialog=await dismissFirstDialog(page,page.locator('[data-component-action="edit_direct_amount"]').first());
    const addDialog=await dismissFirstDialog(page,page.locator("#addComponentButton"));
    const replaceDialog=await dismissFirstDialog(page,page.locator('[data-component-action="replace_resource"]').first());
    const removeDialog=await dismissFirstDialog(page,page.locator('[data-component-action="remove_resource"]').first());
    record("BROWSER-007","governed component dialogs","quantity/direct/add/replace/remove",[quantityDialog,directDialog,addDialog,replaceDialog,removeDialog].join(" | "),quantityDialog.includes("Decimal")&&directDialog.includes("Decimal")&&addDialog.includes("资源编码")&&replaceDialog.includes("资源编码")&&removeDialog.includes("removed"));

    await page.locator('#tabs button[data-tab="summary"]').click();
    const summaryText=await page.locator("#tabContent").innerText();
    const varianceLabels=["价格变化贡献","消耗量变化贡献","资源结构变化贡献","费率变化贡献","总差额"];
    record("BROWSER-008","variance attribution cards","all five",summaryText,varianceLabels.every(value=>summaryText.includes(value)));

    const tabs=page.locator("#tabs button");const tabCount=await tabs.count();let nonEmpty=0;
    for(let index=0;index<tabCount;index+=1){
      await tabs.nth(index).click();await page.waitForTimeout(60);
      const text=(await page.locator("#tabContent").innerText()).trim();const embedded=await page.locator("#tabContent iframe").count();
      if(text||embedded)nonEmpty+=1;
    }
    record("BROWSER-009","required workbench tabs","11 non-empty",`${tabCount}/${nonEmpty}`,tabCount===11&&nonEmpty===11);
    await page.locator('#tabs button[data-tab="composition"]').click();
    const bodyWidth=await page.evaluate(()=>({scroll:document.body.scrollWidth,client:document.body.clientWidth}));
    record("BROWSER-010","viewport containment","no body horizontal overflow",JSON.stringify(bodyWidth),bodyWidth.scroll<=bodyWidth.client+1);
    record("BROWSER-011","browser errors","0/0",`${consoleErrors.length}/${pageErrors.length}`,consoleErrors.length===0&&pageErrors.length===0);

    await page.evaluate(async()=>{
      const me=await fetch("/api/v1/auth/me",{credentials:"same-origin"}).then(response=>response.json());
      await fetch("/api/v1/auth/logout",{method:"POST",credentials:"same-origin",headers:{"X-CSRF-Token":me.csrf_token}});
    });

    const quote=value=>`"${String(value??"").replaceAll('"','""')}"`;
    fs.appendFileSync(RESULT,checks.map(row=>["check_id","check","expected","actual","verification","status"].map(field=>quote(row[field])).join(",")).join("\n")+"\n");
    if(checks.some(row=>row.status!=="pass"))throw new Error(`Browser smoke failed: ${JSON.stringify(checks)}`);
    const verification=`\n## Browser Verification\n\n- Headless Chromium component-workbench checks: \`${checks.length}/${checks.length} pass\`.\n- Verified the default 定额组成 tab, 15 columns, 137-tree, quantity/direct/add/replace/remove flows, five-way variance cards, 11 tabs and zero browser errors.\n- Dialogs were dismissed before mutation; human_confirmed remains false.\n`;
    for(const name of ["checkpoint_enterprise_quota_component_editing.md","stage_enterprise_quota_calculation_basis_and_component_editing_mvp_report.md"]){
      const reportPath=path.join(OUTPUT,name);const content=fs.readFileSync(reportPath,"utf8").split("\n## Browser Verification\n",1)[0].trimEnd();fs.writeFileSync(reportPath,`${content}\n${verification}`);
    }
    process.stdout.write(JSON.stringify({passed:checks.length,total:checks.length}));
  }finally{await browser.close();}
}

main().catch(error=>{console.error(error);process.exit(1);});
