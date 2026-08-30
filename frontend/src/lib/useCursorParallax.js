import { useEffect } from 'react';
import { gsap, prefersReducedMotion } from './gsapConfig';
import { getCursor } from './cursorState';

// Smoothly lerps an element toward the shared cursor position, scaled by
// `strength` (px of travel at full cursor extent). Uses GSAP's own shared
// ticker (one rAF loop for the whole page, however many elements use this)
// rather than each caller running its own animation frame loop.
export function useCursorParallax(ref, { strengthX = 14, strengthY = 10 } = {}) {
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;

    const state = { x: 0, y: 0 };

    function tick() {
      const cursor = getCursor();
      state.x += (cursor.x * strengthX - state.x) * 0.06;
      state.y += (cursor.y * strengthY - state.y) * 0.06;
      gsap.set(ref.current, { x: state.x, y: state.y });
    }

    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, [ref, strengthX, strengthY]);
}
