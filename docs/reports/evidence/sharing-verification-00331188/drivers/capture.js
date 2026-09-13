async (page) => {
  const out = '/Users/garces/.codex/worktrees/a17c/private-alpha-next/docs/reports/evidence/sharing-verification-00331188';
  const receipts = [
    ['buy-and-hold', 'http://127.0.0.1:3317/r/F8ueGQ0iUbcQokKCMyHdt2EK1DI0bx6m'],
    ['monthly-contribution', 'http://127.0.0.1:3317/r/RzTdSpkhr-NweAQDAZ9tocP9487XqtJb'],
  ];
  const records = [];
  const requests = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const headers = request.headers();
    requests.push({url: request.url(), method: request.method(),
      authorization: Boolean(headers.authorization), cookie: Boolean(headers.cookie)});
  });
  await page.context().clearCookies();
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await page.emulateMedia({colorScheme: 'light', reducedMotion: 'reduce'});
  for (const [shape, url] of receipts) {
    for (const language of ['en', 'es-419']) {
      await page.context().setExtraHTTPHeaders({'Accept-Language': language === 'en' ? 'en-US,en;q=0.9' : 'es-419,es;q=0.9'});
      for (const width of [390, 1280]) {
        const height = width === 390 ? 844 : 900;
        const tag = `${shape}-${width}-${language}`;
        await page.setViewportSize({width, height});
        const response = await page.goto(url, {waitUntil:'networkidle'});
        await page.locator('canvas').first().waitFor({state: 'visible'});
        await page.evaluate(() => document.fonts.ready);
        const atFold = await page.evaluate(() => {
          const rect = el => { const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}; };
          const link = document.querySelector('a[href="/"]');
          const bar = link.parentElement.parentElement;
          const main = document.querySelector('main');
          const h1 = document.querySelector('h1');
          return {viewport:{width:innerWidth,height:innerHeight}, scrollWidth:document.documentElement.scrollWidth,
            main:rect(main), heading:rect(h1), headingCount:document.querySelectorAll('h1').length,
            headingText:h1.innerText, headingLanguage:h1.lang,
            bar:rect(bar), action:rect(link), actionText:link.innerText, actionPath:link.getAttribute('href'),
            chart:rect(document.querySelector('canvas')),
            pageLanguage:main.parentElement.lang,
            robots:document.querySelector('meta[name="robots"]')?.content,
            storage:{local:Object.keys(localStorage),session:Object.keys(sessionStorage)},
            forbiddenChrome:{search:document.querySelectorAll('[role="combobox"], [role="searchbox"], input').length,
              dialogs:document.querySelectorAll('[role="dialog"]').length, navigation:document.querySelectorAll('nav,aside').length},
            bodyText:document.body.innerText,
            overflow:Array.from(document.querySelectorAll('h1,h2,dt,dd,p,li,blockquote,a')).filter(el => {const r=el.getBoundingClientRect();return r.left < -1 || r.right > innerWidth+1}).map(el=>({text:el.textContent,rect:rect(el)}))};
        });
        if (atFold.pageLanguage !== language) throw new Error(`${tag}: wrong language ${atFold.pageLanguage}`);
        await page.screenshot({path:`${out}/${tag}-fold.png`, scale:'css'});
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        await page.screenshot({path:`${out}/${tag}-end.png`,scale:'css'});
        const atEnd = await page.evaluate(() => {
          const last=document.querySelector('main > div:last-child p').getBoundingClientRect();
          const bar=document.querySelector('a[href="/"]').parentElement.parentElement.getBoundingClientRect();
          return {scrollY, lastContentBottom:last.bottom, barTop:bar.top, clearance:bar.top-last.bottom};
        });
        records.push({tag,url,status:response.status(),...atFold,atEnd,cookies:await page.context().cookies()});
      }
    }
  }
  // Check the shell boundaries with the denser Spanish receipt, including live resize.
  const edges=[];
  for (const width of [320,375,399,400,719,720,721,1023,1024,1025,1920,390]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    edges.push(await page.evaluate(() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      chartWidth:document.querySelector('canvas').getBoundingClientRect().width,
      titleWidth:document.querySelector('h1').getBoundingClientRect().width})));
  }
  await page.setViewportSize({width:390,height:844});
  await page.goto('http://127.0.0.1:3317/r/unknownreceipt00000000000000',{waitUntil:'networkidle'});
  await page.screenshot({path:`${out}/unknown-receipt-390-es-419.png`,scale:'css'});
  const tombstone={text:await page.locator('body').innerText(),cookies:await page.context().cookies()};
  return {records,edges,tombstone,errors,requests};
}
