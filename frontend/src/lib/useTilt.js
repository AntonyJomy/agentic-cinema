import { useEffect } from 'react';
import { gsap, prefersReducedMotion } from './gsapConfig';

// Local per-element hover tilt + a CSS-variable-driven "spotlight" that
// follows the cursor within the element's own bounds. This is a local
// mousemove listener on one small element (appropriate for a hover
// effect), not the kind of duplicated *global* scroll/cursor listener the
// brief warns against — that's handled once, centrally, by cursorState.js.
export function useTilt(ref, { max = 6 } = {}) {
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return undefined;

    // Note: 'scale' is a GSAP alias for scaleX+scaleY at tween-creation time,
    // but quickTo's resetTo() looks up properties by their literal internal
    // name — passing the alias silently fails to update anything. Using
    // scaleX/scaleY directly is the documented workaround.
    const rotateX = gsap.quickTo(el, 'rotationX', { duration: 0.4, ease: 'power2.out' });
    const rotateY = gsap.quickTo(el, 'rotationY', { duration: 0.4, ease: 'power2.out' });
    const scaleX = gsap.quickTo(el, 'scaleX', { duration: 0.4, ease: 'power2.out' });
    const scaleY = gsap.quickTo(el, 'scaleY', { duration: 0.4, ease: 'power2.out' });

    function onMove(e) {
      const rect = el.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width;
      const py = (e.clientY - rect.top) / rect.height;
      rotateX(-(py - 0.5) * max);
      rotateY((px - 0.5) * max);
      scaleX(1.02);
      scaleY(1.02);
      el.style.setProperty('--spot-x', `${px * 100}%`);
      el.style.setProperty('--spot-y', `${py * 100}%`);
      el.style.setProperty('--spot-opacity', '1');
    }

    function onLeave() {
      rotateX(0);
      rotateY(0);
      scaleX(1);
      scaleY(1);
      el.style.setProperty('--spot-opacity', '0');
    }

    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [ref, max]);
}
