// Shared Lenis instance singleton, set by useLenis.js — lets other
// components (e.g. the scroll-to-top button) drive Lenis's own virtual
// scroll position directly via lenis.scrollTo(), instead of calling
// native window.scrollTo, which Lenis doesn't know about and would
// otherwise fight/override on its very next animation frame.
let lenisInstance = null;

export function setLenis(instance) {
  lenisInstance = instance;
}

export function getLenis() {
  return lenisInstance;
}
