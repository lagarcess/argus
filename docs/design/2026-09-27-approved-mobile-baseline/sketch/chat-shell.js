// Local UI-only conversation navigation. No API, storage or interpretation changes.
(() => {
  let current=null,returnFocus=null;
  const conversations=sampleQuestions.map((q,i)=>({id:'example-'+i,title:['Investing or a CD?','September spending','A savings plan'][i],turns:[{q,a:sampleAnswer(q)}],pinned:i===0,unread:false}));
  const panel=document.createElement('dialog');panel.className='chat-shell-panel';phone.appendChild(panel);
  const glyph=key=>`<svg viewBox="0 0 24 24" aria-hidden="true">${inheritedIcons[key]}</svg>`;
  const menuRow=(label,key,action)=>`<button class="chat-shell-row" data-chat-shell="${action}">${glyph(key)}<span>${label}</span></button>`;
  window.previewChatTitle=()=>current?.title||chatTurns[0]?.q||'';
  const originalSend=sendPreview;
  sendPreview=function(q){q=q||document.getElementById('chattext')?.value.trim();if(!q)return;if(!current){current={id:crypto.randomUUID(),title:q.slice(0,80),turns:chatTurns,pinned:false,unread:false};conversations.unshift(current);registerSearch(current)}originalSend(q)};
  function open(title,body){if(!panel.open)returnFocus=document.activeElement;panel.setAttribute('aria-label',title);panel.innerHTML=`<div class="chat-shell-heading"><h2>${escape(title)}</h2><button data-chat-shell="close" aria-label="Close ${escape(title)}">${glyph('x')}</button></div>${body}`;if(!panel.open)panel.showModal()}
  function close(){panel.close();if(returnFocus?.isConnected&&!returnFocus.hidden)returnFocus.focus({preventScroll:true})}
  function startNew(){close();current=null;chatTurns=[];show('chat')}
  function openConversation(id){const found=conversations.find(c=>c.id===id);if(!found)return;close();current=found;current.unread=false;chatTurns=current.turns;show('chat')}
  function renderRecentList(query=''){const list=conversations.filter(c=>(c.title+' '+c.turns.map(t=>t.q).join(' ')).toLowerCase().includes(query.toLowerCase()));const groups=[['Pinned',list.filter(c=>c.pinned)],['Recent',list.filter(c=>!c.pinned)]];panel.querySelector('#recent-chat-list').innerHTML=groups.map(([label,items])=>items.length?`<section><h3>${label}</h3>${items.map(c=>`<button class="chat-shell-row recent-chat" data-open-conversation="${c.id}" ${current===c?'aria-current="true"':''}><span><strong>${escape(c.title)}</strong><small>${current===c?'Current conversation':'Local preview conversation'}</small></span>${c.unread?'<i class="chat-unread" aria-label="Unread"></i>':''}${current===c?glyph('check'):''}</button>`).join('')}</section>`:'').join('')||'<p class="muted">No conversations match.</p>'}
  function recents(){open('Chats','<label class="sr" for="recent-chat-search">Search chats</label><input id="recent-chat-search" type="search" placeholder="Search chats" autocomplete="off"><div id="recent-chat-list"></div><p class="chat-shell-note">Fictional examples and this session’s chats.<br>Everything resets on reload.</p>');renderRecentList();panel.querySelector('#recent-chat-search').addEventListener('input',e=>renderRecentList(e.target.value))}
  function options(){open('Chat options',`<p class="chat-option-title">${escape(window.previewChatTitle())}</p>`+menuRow(current?.unread?'Mark as read':'Mark as unread',current?.unread?'mailopen':'mail','unread')+menuRow(current?.pinned?'Unpin chat':'Pin chat','pin','pin')+menuRow('Rename chat','edit','rename')+menuRow('Delete chat','trash','delete'))}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-chat-shell],[data-open-conversation]');if(!b)return;e.stopImmediatePropagation();if(b.dataset.openConversation){openConversation(b.dataset.openConversation);return}const a=b.dataset.chatShell;
    if(a==='close'){close();return}if(a==='recents'){recents();return}if(a==='new'){startNew();return}if(a==='options'){options();return}
    if(a==='share'){open('Share conversation','<p class="chat-option-title">'+escape(window.previewChatTitle())+'</p><p class="muted">This is the place to review what you share before creating a link.</p><p class="chat-shell-note">Layout preview only. No public link is created. Production sharing permissions and availability still apply.</p>');return}
    if(!current)return;
    if(a==='pin'||a==='unread'){current[a==='pin'?'pinned':'unread']=!current[a==='pin'?'pinned':'unread'];options()}
    if(a==='rename'){open('Rename chat',`<form id="rename-preview-chat"><label for="chat-title-input">Conversation title</label><input id="chat-title-input" name="title" maxlength="80" required value="${escape(current.title)}"><button class="primary">Save title</button></form>`);panel.querySelector('input').focus()}
    if(a==='delete'){open('Delete this preview chat?',`<p class="muted">This only removes “${escape(current.title)}” from this local design sample.</p><button class="primary" data-chat-shell="confirm-delete">Delete preview chat</button><button class="secondary" data-chat-shell="options">Cancel</button>`)}
    if(a==='confirm-delete'){const i=searchRecords.findIndex(r=>r.conversationId===current.id);if(i>=0)searchRecords.splice(i,1);conversations.splice(conversations.indexOf(current),1);startNew()}
  },true);
  document.addEventListener('submit',e=>{if(e.target.id!=='rename-preview-chat')return;e.preventDefault();const value=new FormData(e.target).get('title').trim();if(!value)return;current.title=value;close();refineHeader()});
  panel.addEventListener('close',()=>{if(returnFocus?.isConnected&&!returnFocus.hidden)returnFocus.focus({preventScroll:true})});
  // Global Search opens the same local examples, rather than appending them to another chat.
  function registerSearch(conversation,record){record=record||{kind:'Conversation',detail:'Local preview conversation',terms:''};Object.defineProperty(record,'title',{get:()=>conversation.title,configurable:true});record.conversationId=conversation.id;if(!searchRecords.includes(record))searchRecords.push(record)}
  for(const record of searchRecords){if(record.sample!==undefined)registerSearch(conversations.find(c=>c.id==='example-'+record.sample),record)}
  window.openPreviewConversation=openConversation;
  refineHeader();
})();
