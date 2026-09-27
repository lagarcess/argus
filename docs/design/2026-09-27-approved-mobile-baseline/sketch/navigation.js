icons.search='<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>';
icons.updates='<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>';
let updatesSeen=false;
const navItems=[['home','Home'],['accounts','Accounts'],['chat','Ask Argus'],['plan','Plan'],['search','Search']];
drawNav=function(){nav.innerHTML=navItems.map(([k,label])=>`<button class="tab ${active===k?'active':''}" data-tab="${k}" aria-label="${label}${k==='updates'&&!updatesSeen?', new example updates':''}" ${active===k?'aria-current="page"':''}>${k==='chat'?ARGUS_MARK:icon(k)}${k==='updates'&&!updatesSeen?'<i class="update-dot" aria-hidden="true"></i>':''}</button>`).join('')};
// A single header survives every surface transition; controls never remount.
const appHeader=document.createElement('header');appHeader.className='app-header';
const headerGlyph=key=>'<svg viewBox="0 0 24 24" aria-hidden="true">'+inheritedIcons[key]+'</svg>';
appHeader.innerHTML='<button class="chat-recents-trigger" data-chat-shell="recents" aria-label="Recent chats" hidden>'+headerGlyph('history')+'</button><button class="chat-new-trigger" data-chat-shell="new" aria-label="New chat" hidden>'+headerGlyph('newchat')+'</button><span class="header-title brand"></span><div class="chattopactions"><button data-chat-shell="share" aria-label="Share conversation" hidden>'+headerGlyph('link')+'</button><button data-chat-shell="options" aria-label="Chat options" aria-haspopup="dialog" hidden>'+headerGlyph('more')+'</button><button class="profile-trigger header-bell" data-open-updates aria-label="Updates, new example updates">'+icon('updates')+'<i class="update-dot" aria-hidden="true"></i></button><button class="profile-trigger" data-profile="open" aria-label="Profile and settings">'+headerGlyph('user')+'</button></div>';
phone.appendChild(appHeader);
function refineHeader(){
 screen.querySelectorAll('.top').forEach(el=>el.remove());
 const label=appHeader.querySelector('.header-title');
 const conversation=page==='chat'&&chatTurns.length>0;
 label.textContent=page==='chat'?(conversation?(window.previewChatTitle?.()||chatTurns[0].q):''):page==='search'?'':page==='home'||page==='start'?'argus':({accounts:'Accounts',plan:'Plan',updates:'Updates',manual:'Accounts',review:'Accounts'})[page]||'';
 label.className='header-title '+(page==='chat'?'conversation-title':page==='home'||page==='start'?'brand':'page-label');
 label.title=label.textContent;
 appHeader.classList.toggle('conversation-header',page==='chat');
 appHeader.querySelector('[data-chat-shell=recents]').hidden=page!=='chat';
 appHeader.querySelector('[data-chat-shell=new]').hidden=page!=='chat';
 appHeader.querySelector('[data-chat-shell=share]').hidden=!conversation;
 appHeader.querySelector('[data-chat-shell=options]').hidden=!conversation;
 appHeader.querySelector('[data-open-updates]').hidden=conversation;
 appHeader.querySelector('[data-profile]').hidden=conversation;
 appHeader.querySelector('.update-dot').hidden=updatesSeen;
 appHeader.querySelector('[data-open-updates]').setAttribute('aria-label','Updates'+(updatesSeen?'':', new example updates'));
}
const oldRenderChat=renderChat;renderChat=function(){oldRenderChat();refineHeader()};
const oldShowNav=show;
show=function(p){oldShowNav(p);if(p==='updates'){page='updates';active='updates';updatesSeen=true;drawNav();screen.innerHTML=`${renderTop()}<p class="eyebrow">YOUR FINANCIAL PERSPECTIVE</p><h1>Worth knowing.</h1><p class="muted">A quiet place for what changed.</p><p class="demolabel">Fictional examples · No monitoring is active</p><section class="section" style="margin-top:28px"><p class="eyebrow">MILESTONE</p><h2>Your safety net is ready.</h2><p class="muted">Your sample emergency fund reached $15,000. Take a moment to decide what comes next.</p><button class="primary surface-cta" data-tab="plan">View your goals</button></section><section class="section"><p class="eyebrow">BUDGET CHECK-IN</p><h2>A little over on dining.</h2><p class="muted">The sample food and dining total is $850, against a $750 budget this month.</p><button class="primary surface-cta" data-update-question="1">Explore with Argus</button></section><section class="section"><p class="eyebrow">MARKET PERSPECTIVE</p><h2>What did you gain by investing?</h2><p class="muted">A future comparison could put investment performance beside a savings or CD alternative, with matching dates and clear assumptions.</p><button class="primary surface-cta" data-update-question="0">Try a sample comparison</button></section><section class="section"><p class="eyebrow">YOUR WEEKLY BRIEF</p><h2>The bigger picture.</h2><p class="muted">A place for account changes, goal progress and market context on your schedule.</p><span class="demolabel">Scheduling is a proposed feature, not active here.</span></section>`;}if(p==='search'){page='search';active='search';drawNav();screen.innerHTML=renderTop()+`<p class="eyebrow">YOUR MONEY, WITH CONTEXT</p><h1>Find your way back.</h1><p class="muted">Accounts, activity, goals and conversations.</p><label class="sr" for="omnisearch">Search your workspace</label><input id="omnisearch" type="search" placeholder="Search your workspace…" autocomplete="off"><p class="demolabel">Fictional sample records · Search by name or topic</p><div id="searchresults"></div><span class="sr" id="searchcount" role="status"></span>`;renderResults('');document.getElementById('omnisearch').addEventListener('input',e=>renderResults(e.target.value));}refineHeader()};
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-open-updates')){e.stopImmediatePropagation();show('updates');return}if(b.dataset.profile){e.stopImmediatePropagation();if(b.dataset.profile==='open')openSettingsPreview()}if(b.dataset.updateQuestion!==undefined){e.stopImmediatePropagation();show('chat');sendPreview(sampleQuestions[Number(b.dataset.updateQuestion)])}},true);
const searchRecords=[
{title:'Everyday checking',kind:'Account',detail:'Checking · Sample balance $4,200',dest:'accounts',terms:'bank cash balance'},
{title:'Emergency fund',kind:'Goal',detail:'Savings goal · Prepared example',dest:'plan',terms:'savings safety'},
{title:'Compare investing with a CD',kind:'Conversation',detail:'Opportunity cost · Illustrative comparison',sample:0,terms:'investment certificate deposit market'},
{title:'September spending',kind:'Conversation',detail:'Understand a sample month',sample:1,terms:'budget dining transactions'},
{title:'A savings plan',kind:'Conversation',detail:'A target and a timeline',sample:2,terms:'goal contribution money'}];
function renderResults(query){const matches=searchRecords.filter(r=>(r.title+' '+r.kind+' '+r.terms).toLowerCase().includes(query.trim().toLowerCase()));document.getElementById('searchresults').innerHTML=matches.length?matches.map(r=>`<button class="choice" data-search-record="${searchRecords.indexOf(r)}"><span><small>${r.kind}</small><strong>${r.title}</strong><small>${r.detail}</small></span>${rowChevron}</button>`).join(''):'<p class="muted">No sample records match. Try “savings” or “CD”.</p>';document.getElementById('searchcount').textContent=matches.length+' results';}
document.addEventListener('click',e=>{const b=e.target.closest('[data-search-record]');if(!b)return;e.stopImmediatePropagation();const r=searchRecords[Number(b.dataset.searchRecord)];if(r.conversationId){openPreviewConversation(r.conversationId)}else{sheet.innerHTML=`<span class="demolabel">FICTIONAL SEARCH RESULT</span><h2 style="margin-top:14px">${r.title}</h2><p class="muted">${r.detail}</p><p class="muted">${r.dest==='accounts'?'USD · Fictional checking account, $4,200 balance.':'Emergency savings · $12,000 of a $15,000 target.'}</p><button class="primary" data-chat-action="close">Back to search</button>`;sheet.showModal()}},true);
show('chat');
