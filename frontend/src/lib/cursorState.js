// One shared cursor-position singleton for the whole page, instead of every
// component that wants cursor-reactive motion attaching its own
// window-level mousemove listener. Mutable object updated imperatively
// (not React state) so reading it in a GSAP ticker never triggers a
// re-render — this is read 60x/sec by anything using useCursorParallax.
const cursor = { x: 0, y: 0, clientX: 0, clientY: 0 }; // x/y normalized -1..1, relative to viewport center; clientX/clientY raw px

let attached = false;

function attachListener() {
  if (attached || typeof window === 'undefined') return;
  window.addEventListener(
    'mousemove',
    (e) => {
      cursor.x = (e.clientX / window.innerWidth) * 2 - 1;
      cursor.y = (e.clientY / window.innerHeight) * 2 - 1;
      cursor.clientX = e.clientX;
      cursor.clientY = e.clientY;
    },
    { passive: true }
  );
  attached = true;
}

export function getCursor() {
  attachListener();
  return cursor;
}
