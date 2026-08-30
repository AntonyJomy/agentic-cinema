import { useEffect, useRef } from 'react';
import { gsap, prefersReducedMotion } from '../lib/gsapConfig';
import { getCursor } from '../lib/cursorState';
import './CustomCursor.css';

// A small reticle that tracks the real cursor 1:1 and blends via
// `mix-blend-mode: difference`, so it stays legible over both the dark page
// background and any lighter panels without any per-section hover logic.
// Skipped entirely on touch devices and under reduced-motion, since it's a
// fine-pointer-only affordance.
export default function CustomCursor() {
  const dotRef = useRef(null);

  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return undefined;

    const el = dotRef.current;
    // scaleX/scaleY, not the 'scale' alias — quickTo's resetTo() can't
    // resolve an aliased property name (see useTilt.js for the full story).
    const scaleX = gsap.quickTo(el, 'scaleX', { duration: 0.3, ease: 'power2.out' });
    const scaleY = gsap.quickTo(el, 'scaleY', { duration: 0.3, ease: 'power2.out' });

    function tick() {
      const cursor = getCursor();
      gsap.set(el, { x: cursor.clientX, y: cursor.clientY });
    }
    gsap.ticker.add(tick);

    function onOver(e) {
      if (e.target.closest('a, button')) { scaleX(1.8); scaleY(1.8); }
    }
    function onOut(e) {
      if (e.target.closest('a, button')) { scaleX(1); scaleY(1); }
    }
    document.addEventListener('mouseover', onOver);
    document.addEventListener('mouseout', onOut);

    return () => {
      gsap.ticker.remove(tick);
      document.removeEventListener('mouseover', onOver);
      document.removeEventListener('mouseout', onOut);
    };
  }, []);

  return (
    <div className="landing-cursor" ref={dotRef} aria-hidden="true">
      <span className="landing-cursor-arm landing-cursor-arm--h" />
      <span className="landing-cursor-arm landing-cursor-arm--v" />
    </div>
  );
}
