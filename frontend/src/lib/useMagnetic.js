import { useEffect } from 'react';
import { gsap, prefersReducedMotion } from './gsapConfig';

// Hover-only magnetic pull: the element leans toward the cursor within its
// own bounds and springs back on leave. Reserved for primary CTAs rather
// than applied broadly, so it reads as an invitation, not page-wide noise.
export function useMagnetic(ref, { strength = 0.35 } = {}) {
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return undefined;

    const moveX = gsap.quickTo(el, 'x', { duration: 0.4, ease: 'power3.out' });
    const moveY = gsap.quickTo(el, 'y', { duration: 0.4, ease: 'power3.out' });

    function onMove(e) {
      const rect = el.getBoundingClientRect();
      const relX = e.clientX - (rect.left + rect.width / 2);
      const relY = e.clientY - (rect.top + rect.height / 2);
      moveX(relX * strength);
      moveY(relY * strength);
    }

    function onLeave() {
      moveX(0);
      moveY(0);
    }

    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [ref, strength]);
}
