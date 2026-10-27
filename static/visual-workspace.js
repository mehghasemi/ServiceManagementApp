/* Open evidence for explicit record navigation, filters, sorting and pagination. */
(() => {
  const reveal = () => {
    const id = location.hash.slice(1);
    const target = id && document.getElementById(id);
    if (target) { let node = target; while (node) { if (node.tagName === 'DETAILS') node.open = true; node = node.parentElement; } }
  };
  document.querySelectorAll('.evidence-disclosure').forEach(panel => {
    if (location.search || panel.querySelector('.errorlist')) panel.open = true;
  });
  reveal(); window.addEventListener('hashchange', reveal);
})();
