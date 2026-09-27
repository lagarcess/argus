// Decorative empty-chat study only; never a runtime/loading signal.
(() => {
  function applyLogoLight() {
    const logo = document.querySelector('#markslot .argusmark');
    if (!logo || logo.classList.contains('edge-light-mark')) return;
    logo.classList.add('edge-light-mark');
    const paths = logo.querySelector('g').cloneNode(true);
    paths.removeAttribute('data-logo');
    paths.removeAttribute('data-source');
    paths.setAttribute('class', 'logo-edge-highlight');
    paths.setAttribute('mask', 'url(#greeting-edge-light)');
    logo.insertAdjacentHTML('afterbegin', `<defs>
      <linearGradient id="greeting-wave-x"><stop stop-color="white" stop-opacity="0"/><stop offset=".5" stop-color="white"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient>
      <linearGradient id="greeting-wave-y" x1="0" y1="0" x2="0" y2="1"><stop stop-color="white" stop-opacity="0"/><stop offset=".5" stop-color="white"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient>
      <mask id="greeting-edge-light" maskUnits="userSpaceOnUse" x="0" y="0" width="473" height="447" style="mask-type:alpha">
        <rect class="logo-light-wave wave-left" x="-160" y="0" width="160" height="447" fill="url(#greeting-wave-x)"/>
        <rect class="logo-light-wave wave-right" x="473" y="0" width="160" height="447" fill="url(#greeting-wave-x)"/>
        <rect class="logo-light-wave wave-bottom" x="0" y="447" width="473" height="160" fill="url(#greeting-wave-y)"/>
      </mask>
    </defs>`);
    logo.appendChild(paths);
  }
  const previous = renderChat;
  renderChat = function () { previous(); applyLogoLight(); };
  applyLogoLight();
})();
