// Shared preview chrome. Profile root and personal details deliberately stay clear.
(() => {
  const topEdge=document.createElement('div'),bottomEdge=document.createElement('div');
  topEdge.className='scroll-edge scroll-edge-top';bottomEdge.className='scroll-edge scroll-edge-bottom';
  for(const edge of [topEdge,bottomEdge]){edge.setAttribute('aria-hidden','true');phone.appendChild(edge)}
  let frame=0;
  function update(){
    frame=0;
    const profile=phone.classList.contains('settings-mode')&&!!screen.querySelector('.settings-root,.profile-summary');
    const chat=phone.classList.contains('chatmode');
    const scroller=chat?screen.querySelector('.chattranscript'):screen;
    const range=scroller?scroller.scrollHeight-scroller.clientHeight:0;
    topEdge.classList.toggle('edge-visible',!profile);
    bottomEdge.classList.toggle('edge-visible',!profile&&!phone.classList.contains('feedback-mode')&&range>2&&scroller.scrollTop<range-2);
    // Keep chat's lower fade at the transcript edge, above the composer.
    bottomEdge.style.bottom=chat&&scroller?`${Math.max(0,phone.getBoundingClientRect().bottom-parseFloat(getComputedStyle(phone).borderBottomWidth)-scroller.getBoundingClientRect().bottom)}px`:'0px';
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(update)}
  const sizeObserver=new ResizeObserver(schedule);
  function observeContent(){sizeObserver.disconnect();sizeObserver.observe(screen);for(const child of screen.children)sizeObserver.observe(child);const transcript=screen.querySelector('.chattranscript');if(transcript){sizeObserver.observe(transcript);for(const child of transcript.children)sizeObserver.observe(child)}schedule()}
  new MutationObserver(observeContent).observe(screen,{childList:true,subtree:true});
  new MutationObserver(schedule).observe(phone,{attributes:true,attributeFilter:['class']});
  screen.addEventListener('scroll',schedule,{passive:true,capture:true});
  window.addEventListener('resize',schedule,{passive:true});observeContent();
})();
