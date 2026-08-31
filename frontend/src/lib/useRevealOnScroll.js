import { useEffect } from 'react';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from './gsapConfig';

// Traditional sectioned page, not a pinned/scrubbed one — each section
// fades and lifts in every time it enters the viewport, in either scroll
// direction (not a one-time reveal): `restart none restart none` snaps
// the tween back to its fromVars (opacity 0, offset y) the moment the
// section is entered from below OR re-entered from above, then plays it
// forward again — the two "leaving" events are left at `none`, so
// elements just hold their fully-revealed state until the next entry
// rather than needing a separate reset step on exit.
export function useRevealOnScroll(ref, { y = 24, stagger, selector } = {}) {
  useEffect(() => {
    if (!ref.current) return undefined;
    registerGsap();

    if (prefersReducedMotion()) {
      return undefined;
    }

    const targets = selector ? ref.current.querySelectorAll(selector) : ref.current;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { opacity: 0, y },
        {
          opacity: 1,
          y: 0,
          duration: 0.7,
          ease: 'power2.out',
          stagger,
          overwrite: true,
          scrollTrigger: {
            trigger: ref.current,
            start: 'top 82%',
            end: 'bottom 18%',
            toggleActions: 'restart none restart none',
          },
        }
      );
    });

    return () => ctx.revert();
  }, [ref, y, stagger, selector]);
}

export { ScrollTrigger };
