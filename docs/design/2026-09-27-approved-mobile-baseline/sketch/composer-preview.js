// UI study only: authored inputs and review cards; no capture APIs, extraction or AI.
(() => {
  const drafts=new WeakMap(),proposals=new Map();
  const glyph=k=>`<svg viewBox="0 0 24 24" aria-hidden="true">${inheritedIcons[k]}</svg>`;
  const capture=document.createElement('dialog');capture.className='capture-panel';phone.appendChild(capture);
  let origin=null;
  const presets={receipt:{name:'Coffee receipt',amount:'185',merchant:'Café Central',category:'Dining',currency:'DOP',account:'Cash wallet'},photo:{name:'Receipt photo',amount:'185',merchant:'Café Central',category:'Dining',currency:'DOP',account:'Cash wallet'},file:{name:'September statement.pdf',amount:'1250',merchant:'Supermercado',category:'Groceries',currency:'DOP',account:'Checking'},voice:{name:'Voice note',amount:'350',merchant:'Lunch',category:'Dining',currency:'DOP',account:'Cash wallet'},typed:{name:'Typed example',amount:'350',merchant:'Lunch',category:'Dining',currency:'DOP',account:'Cash wallet'}};
  const voiceText='Gasté 350 pesos en almuerzo, en efectivo.';
  function state(){if(!drafts.has(chatTurns))drafts.set(chatTurns,{text:'',items:[],voiceExample:false});return drafts.get(chatTurns)}
  function open(title,body){if(document.querySelector('.attachment-tray-open'))setTray(false,true);origin=document.activeElement;capture.setAttribute('aria-label',title);capture.innerHTML=`<header><h2>${escape(title)}</h2><button data-capture="close" aria-label="Close ${escape(title)}">${glyph('x')}</button></header>${body}`;if(!capture.open)capture.showModal()}
  function close(){capture.close()}
  capture.addEventListener('close',()=>{if(origin?.isConnected)origin.focus({preventScroll:true})});
  function setTray(expanded,restoreFocus=false){
    const box=document.querySelector('.capture-composer'),tray=box?.querySelector('.attachment-tray'),trigger=box?.querySelector('[data-capture="add"]');
    if(!tray)return;
    if(expanded){document.getElementById('chattext')?.blur();setNavCompact(false)}
    box.classList.toggle('attachment-tray-open',expanded);
    tray.inert=!expanded;tray.setAttribute('aria-hidden',String(!expanded));
    trigger.setAttribute('aria-expanded',String(expanded));
    trigger.setAttribute('aria-label',expanded?'Close attachments':'Add attachments');
    trigger.innerHTML=glyph(expanded?'x':'plus');
    if(restoreFocus)trigger.focus({preventScroll:true});
  }
  function addMenu(){setTray(!document.querySelector('.capture-composer')?.classList.contains('attachment-tray-open'))}
  const attachmentTray=()=>`<section id="attachment-tray" class="attachment-tray" aria-label="Add to your message" aria-hidden="true" inert><div><div class="attachment-choices">${[['receipt','camera','Scan receipt'],['photo','image','Choose photo'],['file','upload','Upload file']].map(([action,key,label])=>`<button data-capture="${action}">${glyph(key)}<span>${label}</span></button>`).join('')}</div></div></section>`;
  // Keep press targets still: toolbar taps must not move the composer before click.
  let gesture=null;
  document.addEventListener('pointerdown',e=>{
    gesture={x:e.clientX,y:e.clientY,id:e.pointerId};
    if(e.target.closest('.capture-toolbar button')&&document.activeElement?.id==='chattext'&&e.button===0)e.preventDefault();
  },true);
  document.addEventListener('pointercancel',()=>{gesture=null},true);
  document.addEventListener('pointerup',e=>{
    const tap=gesture&&gesture.id===e.pointerId&&Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)<8;gesture=null;
    if(!tap||e.target.closest('.capture-composer,dialog,button,a,input,textarea,select,[role="button"]'))return;
    setTray(false);document.getElementById('chattext')?.blur();
  },true);
  document.addEventListener('keydown',e=>{
    if(e.key!=='Escape'||document.querySelector('dialog[open]'))return;
    if(document.querySelector('.attachment-tray-open')){e.preventDefault();e.stopPropagation();setTray(false,true)}
    else if(document.activeElement?.id==='chattext'){e.preventDefault();document.activeElement.blur()}
  },true);
  let restingHeight=window.innerHeight;
  function syncComposerInteraction(){
    const editing=phone.classList.contains('chatmode')&&document.activeElement?.id==='chattext';
    phone.classList.toggle('composer-editing',editing);
    const view=window.visualViewport,visible=view?.height||window.innerHeight;
    const keyboard=editing&&matchMedia('(pointer:coarse)').matches&&Math.abs((view?.scale||1)-1)<.05&&Math.max(restingHeight,innerHeight)-visible>140;
    phone.classList.toggle('composer-keyboard',keyboard);
    if(!editing)restingHeight=innerHeight;
    phone.style.setProperty('--composer-viewport-height',visible+'px');
    syncNavVisibility();
  }
  document.addEventListener('focusin',e=>{
    if(e.target.id==='chattext'){setTray(false);setNavCompact(false)}
    syncComposerInteraction();
  });
  document.addEventListener('focusout',()=>requestAnimationFrame(syncComposerInteraction));
  window.visualViewport?.addEventListener('resize',syncComposerInteraction);
  window.addEventListener('resize',syncComposerInteraction);

  function attach(item){const s=state();if(item.proposal)s.items=s.items.filter(i=>!i.proposal);if(!s.items.some(i=>i.id===item.id))s.items.push(item);close();refresh();}
  function chips(){return state().items.map(i=>`<span class="capture-chip">${glyph(i.icon)}<span>${escape(i.label)}</span><button data-remove-capture="${i.id}" aria-label="Remove ${escape(i.label)}">${glyph('x')}</button></span>`).join('')}
  function update(){const s=state(),input=document.getElementById('chattext');if(!input)return;const send=document.getElementById('chatsend'),ready=!!(input.value.trim()||s.items.length);send.hidden=!ready;send.disabled=!ready;document.getElementById('chatvoice').hidden=ready;input.style.height='45px';input.style.height=Math.min(120,input.scrollHeight)+'px';}
  function refresh(){if(!phone.classList.contains('chatmode'))return;const box=document.querySelector('.chatcomposer');if(!box)return;const s=state();box.classList.add('capture-composer');box.classList.remove('attachment-tray-open');box.innerHTML=`${attachmentTray()}<div class="capture-chips" ${s.items.length?'':'hidden'}>${chips()}</div><div class="capture-input-row"><textarea id="chattext" aria-label="Message Argus" placeholder="Type a message" rows="1">${escape(s.text)}</textarea></div><div class="capture-toolbar"><button data-capture="add" aria-label="Add attachments" aria-controls="attachment-tray" aria-expanded="false">${glyph('plus')}</button><div class="capture-voice-actions"><button id="chatmic" data-capture="voice" aria-label="Dictate a message" title="Dictate a message">${glyph('mic')}</button><button id="chatvoice" class="voice-mode" data-capture="conversation" aria-label="Voice conversation preview" title="Voice conversation">${glyph('waveform')}</button><button id="chatsend" class="sendchat" data-chat-action="send" aria-label="Send message" hidden>${glyph('arrowup')}</button></div></div>`;
    const input=document.getElementById('chattext');input.addEventListener('input',()=>{s.text=input.value;s.voiceExample=false;update()});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendPreview()}});update();
    const starters=document.querySelector('.starters');if(starters&&!starters.querySelector('[data-capture]'))starters.insertAdjacentHTML('afterbegin','<button class="starter" data-capture="typed">Try recording an expense</button>');
    syncComposerInteraction();
    const disclaimer=document.querySelector('.chatdisclaimer');if(disclaimer)disclaimer.textContent='Design preview · Sample captures only · Nothing sent';
  }
  const originalRender=renderChat;renderChat=function(){originalRender();refresh()};
  function card(p){const total=new Intl.NumberFormat('en-US',{style:'currency',currency:p.currency}).format(Number(p.amount));return `<article class="record-proposal"><span class="proposal-eyebrow">${p.confirmed?'CONFIRMED IN THIS PREVIEW':'PROPOSED ENTRY · NOT SAVED'}</span><h3>${escape(p.merchant)}</h3><div class="proposal-amount">${escape(total)}</div><dl><div><dt>Paid from</dt><dd>${escape(p.account)}</dd></div><div><dt>Category</dt><dd>${escape(p.category)}</dd></div><div><dt>Date</dt><dd>Today · Example</dd></div><div><dt>Source</dt><dd>${escape(p.name)}</dd></div></dl><p class="capture-note">${p.confirmed?'Example only. Your actual balances have not changed.':'Check the details before confirming. This is an authored sample, not extracted data.'}</p><div class="proposal-actions">${p.confirmed?`<button data-proposal-edit="${p.id}">Correct entry</button>`:`<button data-proposal-edit="${p.id}">Edit details</button><button class="confirm-proposal" data-proposal-confirm="${p.id}">Confirm entry</button>`}</div></article>`}
  function renderProposal(p){p.turn.a=`<p>${p.confirmed?'Your example entry is confirmed.':'Here’s the sample entry to review.'}</p>`+card(p);renderChat()}
  const originalSend=sendPreview;
  sendPreview=function(q){const s=state(),manual=q!==undefined,items=manual?[]:[...s.items],text=q||document.getElementById('chattext')?.value.trim()||'';if(!text&&!items.length)return;
    const source=items.find(i=>i.proposal)?.proposal||(!manual&&s.voiceExample?'voice':null);s.items=[];s.text='';s.voiceExample=false;
    originalSend(text||'Review this sample document.');
    const turn=chatTurns[chatTurns.length-1];turn.captureLabels=items.map(i=>i.label);
    if(source){const p={...presets[source],id:crypto.randomUUID(),confirmed:false,turn};proposals.set(p.id,p);renderProposal(p)}
  };
  document.addEventListener('click',e=>{const b=e.target.closest('[data-capture],[data-remove-capture],[data-proposal-edit],[data-proposal-confirm]');if(!b)return;e.stopImmediatePropagation();
    if(b.dataset.removeCapture){const s=state();s.items=s.items.filter(i=>i.id!==b.dataset.removeCapture);refresh();return}
    if(b.dataset.proposalConfirm){const p=proposals.get(b.dataset.proposalConfirm);if(p){p.confirmed=true;renderProposal(p)}return}
    if(b.dataset.proposalEdit){const p=proposals.get(b.dataset.proposalEdit);if(!p)return;open(p.confirmed?'Correct example entry':'Edit proposed entry',`<form id="edit-capture" data-id="${p.id}"><label for="capture-merchant">Description</label><input id="capture-merchant" name="merchant" value="${escape(p.merchant)}" required maxlength="80"><label for="capture-amount">Amount · ${p.currency}</label><input id="capture-amount" name="amount" type="number" min="0.01" max="1000000000" step="0.01" value="${p.amount}" required><label for="capture-category">Category</label><select id="capture-category" name="category">${['Dining','Groceries','Transport','Other'].map(v=>`<option ${p.category===v?'selected':''}>${v}</option>`).join('')}</select><button class="primary">${p.confirmed?'Save correction':'Save proposed details'}</button></form>`);return}
    const a=b.dataset.capture;if(a==='close'){close();return}if(a==='add'){addMenu();return}
    if(['receipt','photo','file'].includes(a)){const p=presets[a];open(a==='receipt'?'Scan a receipt':a==='photo'?'Choose a photo':'Upload a file',`<div class="sample-document">${glyph(a==='receipt'?'camera':a==='photo'?'image':'file')}<strong>${escape(p.name)}</strong><span>Fictional sample · ${p.currency} ${p.amount}</span></div><p class="capture-note">Explore with a prepared example. No camera, photo library or files are accessed.</p><button class="primary" data-capture="attach-${a}">Use sample ${a==='file'?'statement':a==='photo'?'photo':'receipt'}</button>`);return}
    if(a.startsWith('attach-')){const key=a.slice(7);attach({id:key,label:presets[key].name,icon:key==='photo'?'image':'file',proposal:key});return}
    if(a==='conversation'){open('Voice conversation',`<div class="voice-example">${glyph('waveform')}<strong>Talk things through with Argus.</strong><p>A future mode where you speak and Argus answers aloud.</p></div><p class="capture-note">Design concept only. No call starts and your microphone stays off. Dictation adds text to a message; this would be a spoken conversation.</p><button class="primary" data-capture="close">Back to chat</button>`);return}
    if(a==='voice'){open('Voice message',`<div class="voice-example">${glyph('mic')}<strong>Say it in your own words.</strong><p>“Gasté 350 pesos en almuerzo.”</p></div><p class="capture-note">Voice interaction preview. Your microphone stays off.</p><button class="primary" data-capture="voice-review">Try a sample voice note</button>`);return}
    if(a==='voice-review'){open('Review voice transcript',`<label for="voice-transcript">What Argus heard · Sample</label><textarea id="voice-transcript" rows="4">${voiceText}</textarea><p class="capture-note">Edit before adding it to your message. Nothing is sent automatically.</p><button class="primary" data-capture="voice-use">Use transcript</button><button class="secondary" data-capture="voice">Try again</button>`);return}
    if(a==='voice-use'){const text=capture.querySelector('textarea').value.trim();const s=state();s.text=[s.text.trim(),text].filter(Boolean).join(' ');s.voiceExample=s.text===voiceText;close();refresh();return}
    if(a==='typed'){const s=state();s.text=voiceText;s.items=s.items.filter(i=>!i.proposal);s.items.push({id:'typed',label:'Sample cash expense',icon:'wallet',proposal:'typed'});refresh();return}
  },true);
  document.addEventListener('submit',e=>{if(e.target.id!=='edit-capture')return;e.preventDefault();const p=proposals.get(e.target.dataset.id),f=new FormData(e.target),merchant=f.get('merchant').trim();if(!p||!merchant)return;p.merchant=merchant;p.amount=f.get('amount');p.category=f.get('category');close();renderProposal(p)});
  const previousShow=show;show=function(p){phone.classList.remove('composer-editing','composer-keyboard');previousShow(p);syncComposerInteraction()};
  refresh();
})();
