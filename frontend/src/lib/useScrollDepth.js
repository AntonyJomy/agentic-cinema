import { useEffect } from 'react';
import { gsap, registerGsap, prefersReducedMotion } from './gsapConfig';

// Scrubbed parallax: as `trigger` (defaults to the element itself) moves
// through the viewport, `ref` drifts by `speed` × its own height — the
// shared depth mechanism behind every "moves slower/faster than scroll"
// effect on this page, so relative speed differences read as one
// consistent depth system rather than each section inventing its own.
export function useScrollDepth(ref, { trigger, speed = 0.15, start = 'top bottom', end = 'bottom top' } = {}) {
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const triggerEl = trigger?.current || ref.current;

    const ctx = gsap.context(() => {
      gsap.to(ref.current, {
        yPercent: speed * 100,
        ease: 'none',
        scrollTrigger: {
          trigger: triggerEl,
          start,
          end,
          scrub: true,
        },
      });
    });

    return () => ctx.revert();
  }, [ref, trigger, speed, start, end]);
}
