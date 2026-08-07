import { chromium } from "playwright";
const b = await chromium.launch();
const ok=(n,p,d)=>console.log(`${p?"PASS":"FAIL"}  ${n}  ${d??""}`);
const mob=()=>b.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,colorScheme:"dark",locale:"en-US"});
const openMenu=async(p)=>{await p.goto("http://172.16.0.5:3010/chat",{waitUntil:"networkidle"});await p.waitForTimeout(1800);
  await p.getByTestId("chat-shell-menu-trigger").click();await p.waitForTimeout(500);
  const s=await p.evaluate(()=>{const x=[...document.querySelectorAll('[data-testid="sidebar-drawer"] button')].pop();const r=x.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
  await p.touchscreen.tap(s.x,s.y);await p.waitForTimeout(700);};

// 1. Tab cannot leave the drawer while the (non-trapping) profile menu is top.
{ const p=await (await mob()).newPage(); await openMenu(p);
  const inside=[];
  for(let i=0;i<14;i++){await p.keyboard.press("Tab");await p.waitForTimeout(70);
    inside.push(await p.evaluate(()=>{const d=document.querySelector('[data-testid="sidebar-drawer"]');return d?d.contains(document.activeElement):null;}));}
  ok("1 Tab stays inside the drawer with the menu open", inside.every(v=>v===true), `${inside.filter(Boolean).length}/14`); }

// 2. Two fast Escapes: submenu then menu, no press lost to a stale callback.
{ const p=await (await mob()).newPage(); await openMenu(p);
  const dc=await p.evaluate(()=>{const x=[...document.querySelectorAll("[data-profile-menu-surface] button")][1];const r=x.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});
  await p.touchscreen.tap(dc.x,dc.y); await p.waitForTimeout(500);
  await p.keyboard.press("Escape"); await p.keyboard.press("Escape");   // back to back
  await p.waitForTimeout(500);
  const r=await p.evaluate(()=>({menu:!!document.querySelector("[data-profile-menu-surface]"),drawer:!!document.querySelector('[data-testid="sidebar-drawer"]')}));
  ok("2 two fast Escapes close submenu then menu", !r.menu && r.drawer, JSON.stringify(r)); }
await b.close();
