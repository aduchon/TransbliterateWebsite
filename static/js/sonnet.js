// Progressive enhancement for sonnet pages: load model-viewer only when a
// viewer approaches the viewport, so text and images stay instant.
const viewers = document.querySelectorAll('model-viewer');
if (viewers.length) {
  const load = () => import('/static/vendor/model-viewer/model-viewer.min.js');
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) {
      io.disconnect();
      load();
    }
  }, { rootMargin: '400px' });
  viewers.forEach((v) => io.observe(v));
}
