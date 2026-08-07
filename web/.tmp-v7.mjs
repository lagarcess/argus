import { chromium } from "playwright";
const b = await chromium.launch();
const ok=(n,p,d)=>console.log(`${p?"PASS":"FAIL"}  ${n}  ${d??""}`);
const p = await (await b.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,colorScheme:"dark",locale:"en-US"})).newPage();
await p.goto("http://172.16.0.5:3010/chat",{waitUntil:"networkidle"}); await p.waitForTimeout(1800);
await p.getByTestId("chat-shell-menu-trigger").click(); await p.waitForTimeout(500);
const s=await p.evaluate(()=>{const x=[...document.querySelectorAll('[data-testid="sidebar-drawer"] button')].pop();const r=x.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
await p.touchscreen.tap(s.x,s.y); await p.waitForTimeout(600);
// Profile dialog, then its inline language picker.
const prof=await p.evaluate(()=>{const x=[...document.querySelectorAll("[data-profile-menu-surface] button")][0];const r=x.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
await p.touchscreen.tap(prof.x,prof.y); await p.waitForTimeout(900);
const dlg=()=>p.evaluate(()=>!!document.getElementById("argus-profile-modal-title"));
console.log("  profile dialog open:", await dlg());
const trig=await p.evaluate(()=>{const x=document.getElementById("argus-profile-language-trigger");if(!x)return null;const r=x.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
if(!trig){ ok("3 Escape closes the picker, not the dialog", false, "language trigger not found"); }
else {
  await p.touchscreen.tap(trig.x,trig.y); await p.waitForTimeout(500);
  const pickerOpen=await p.evaluate(()=>[...document.querySelectorAll("button")].filter(e=>/espa|english/i.test(e.textContent||"")).length>1);
  await p.keyboard.press("Escape"); await p.waitForTimeout(500);
  const after=await p.evaluate(()=>({picker:[...document.querySelectorAll("button")].filter(e=>/espa|english/i.test(e.textContent||"")).length>1, dialog:!!document.getElementById("argus-profile-modal-title")}));
  ok("3 Escape closes the picker, not the dialog", pickerOpen && !after.picker && after.dialog, JSON.stringify({pickerOpen,...after}));
  await p.keyboard.press("Escape"); await p.waitForTimeout(500);
  ok("3b next Escape closes the dialog", !(await dlg()));
}
await b.close();
