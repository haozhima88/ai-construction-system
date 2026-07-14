import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUTPUT = path.join(ROOT, "data/private/reference_extraction/runs/ENTERPRISE_PRICE_PROVINCIAL_FALLBACK_AND_A111_MANUAL_PRICING_WORKBENCH_1");
const RESULT = path.join(OUTPUT, "enterprise_manual_pricing_web_smoke.csv");
const BASE_URL = process.env.PLATFORM_UAT_BASE_URL || "http://127.0.0.1:8018";

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
  const waitRows=async expected=>page.waitForFunction(value=>document.querySelectorAll('#tabContent tr[data-resource-row]').length===value,expected,{timeout:15000});
  try{
    await page.goto(`${BASE_URL}/login?next=/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});
    await page.locator("#username").fill("uat_editor");await page.locator("#password").fill(env.PLATFORM_UAT_TEMP_PASSWORD);
    await Promise.all([
      page.waitForURL(`${BASE_URL}/quota-building`,{timeout:15000}),
      page.locator('button[type="submit"]').click(),
    ]);
    await page.goto(`${BASE_URL}/enterprise-quota/a111-pilot`,{waitUntil:"domcontentloaded"});
    await page.locator(".eq-workbench").waitFor({state:"visible"});
    await page.locator(".eq-tree-item").first().waitFor({state:"visible",timeout:15000});
    await page.locator("#quotaCode").filter({hasText:"A1-1-"}).waitFor({timeout:15000});
    consoleErrors.length=0;pageErrors.length=0;

    const metricText=(await page.locator("#metrics").innerText()).replaceAll("\n"," | ");
    record("BROWSER-001","fallback metrics","137 / 55 / 54 / 54/55 / 0/55",metricText,["137","55","54","54/55","0/55"].every(value=>metricText.includes(value)));
    const treeCount=await page.locator(".eq-tree-item").count();
    record("BROWSER-002","A1.1 quota tree","137",String(treeCount),treeCount===137);
    const filterOptions=await page.locator("#priceFilter option").allTextContents();
    record("BROWSER-003","nine required filters","9",`${filterOptions.length}: ${filterOptions.join("/")}`,filterOptions.length===9);

    const tabs=page.locator("#tabs button");const tabCount=await tabs.count();let nonEmpty=0;
    for(let index=0;index<tabCount;index+=1){
      await tabs.nth(index).click();await page.waitForTimeout(80);
      const text=(await page.locator("#tabContent").innerText()).trim();
      const embedded=await page.locator("#tabContent iframe").count();if(text||embedded)nonEmpty+=1;
    }
    record("BROWSER-004","required workbench tabs","11 non-empty",`${tabCount}/${nonEmpty}`,tabCount===11&&nonEmpty===11);

    await page.locator('#tabs button[data-tab="manualPricing"]').click();await waitRows(55);
    const manualHeaders=await page.locator("#tabContent thead").first().innerText();
    const requiredHeaders=["省定额价","省定额回填价","企业人工调整价","当前采用价","价格来源","核价状态","生效日期","税口径","区域","调整原因","内部历史观察值","版本历史 / Audit"];
    record("BROWSER-005","manual-pricing columns","all required columns",manualHeaders,requiredHeaders.every(value=>manualHeaders.includes(value)));
    const actionCount=await page.locator('[data-price-action="manual"]').count();
    const acceptCount=await page.locator('[data-price-action="accept"]').count();
    record("BROWSER-006","editor price actions","55 manual and 54 accept",`${actionCount}/${acceptCount}`,actionCount===55&&acceptCount===54);

    const filter=async(name,count)=>{
      await page.locator("#priceFilter").selectOption(name);await page.locator("#priceFilterButton").click();await waitRows(count);
      return page.locator('#tabContent tr[data-resource-row]');
    };
    let rows=await filter("reference_price_missing",1);const missingText=await rows.first().innerText();
    record("BROWSER-007","missing Reference price filter","1 labor row with blank price",missingText,missingText.includes("00010010")&&missingText.includes("人工费")&&missingText.includes("省定额价缺失"));
    rows=await filter("provincial_fallback",54);record("BROWSER-008","provincial fallback filter","54",String(await rows.count()),await rows.count()===54);
    rows=await filter("pending_manual_pricing",55);record("BROWSER-009","pending manual-pricing filter","55",String(await rows.count()),await rows.count()===55);

    let dialogText="";page.once("dialog",async dialog=>{dialogText=dialog.message();await dialog.dismiss();});
    await page.locator('[data-price-action="manual"]').first().click();await page.waitForTimeout(100);
    record("BROWSER-010","manual price action opens governed reason flow","required reason prompt",dialogText,dialogText.includes("必填"));

    await page.locator('#tabs button[data-tab="prices"]').click();const comparisonText=await page.locator("#tabContent").innerText();
    record("BROWSER-011","quota price comparison","server values and statuses",comparisonText,comparisonText.includes("省单价")&&comparisonText.includes("回填价")&&comparisonText.includes("当前采用价")&&comparisonText.includes("核价状态"));
    const bodyWidth=await page.evaluate(()=>({scroll:document.body.scrollWidth,client:document.body.clientWidth}));
    record("BROWSER-012","viewport containment","no body horizontal overflow",JSON.stringify(bodyWidth),bodyWidth.scroll<=bodyWidth.client+1);
    record("BROWSER-013","browser errors","0/0",`${consoleErrors.length}/${pageErrors.length}`,consoleErrors.length===0&&pageErrors.length===0);

    await filter("all",55);
    const screenshot=path.join(OUTPUT,"enterprise_manual_pricing_workbench.png");
    await page.screenshot({path:screenshot,fullPage:false});
    fs.writeFileSync(path.join(OUTPUT,"enterprise_manual_pricing_browser_result.json"),JSON.stringify({checks,consoleErrors,pageErrors},null,2));
    const quote=value=>`"${String(value??"").replaceAll('"','""')}"`;
    fs.appendFileSync(RESULT,checks.map(row=>["check_id","check","expected","actual","verification","status"].map(field=>quote(row[field])).join(",")).join("\n")+"\n");
    if(checks.some(row=>row.status!=="pass"))throw new Error(`Browser smoke failed: ${JSON.stringify(checks)}`);

    const summaryPath=path.join(OUTPUT,"stage_summary.json");const summary=JSON.parse(fs.readFileSync(summaryPath,"utf8"));
    summary.browser_smoke_passed=checks.length;summary.browser_smoke_total=checks.length;summary.browser_screenshot=screenshot;
    fs.writeFileSync(summaryPath,JSON.stringify(summary,null,2));
    const verification=`\n## Browser Verification\n\n- Headless Chromium manual-pricing checks: \`${checks.length}/${checks.length} pass\`.\n- Verified 137-tree rendering, 11 tabs, nine filters, 55 price rows, 54 fallback rows, one missing-price row, governed editor actions, and no browser errors.\n- Screenshot: \`enterprise_manual_pricing_workbench.png\`.\n`;
    for(const name of ["checkpoint_enterprise_price_provincial_fallback.md","stage_enterprise_price_provincial_fallback_and_a111_manual_pricing_workbench_report.md"]){
      const reportPath=path.join(OUTPUT,name);const content=fs.readFileSync(reportPath,"utf8").split("\n## Browser Verification\n",1)[0].trimEnd();fs.writeFileSync(reportPath,`${content}\n${verification}`);
    }
    process.stdout.write(JSON.stringify({passed:checks.length,total:checks.length,screenshot}));
  }finally{await browser.close();}
}

main().catch(error=>{console.error(error);process.exit(1);});
