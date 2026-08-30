import { useEffect } from 'react';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from './gsapConfig';

// Traditional sectioned page, not a pinned/scrubbed one — each section just
// fades and lifts in once when it enters the viewport. `play none none
// none` (not scrub) is deliberate: this page is Palomino-structured
// (hero -> services -> stats -> footer), so its motion language should be
// "reveal once," matching that kind of layout, not the scrub choreography
// used elsewhere in this app for pinned cinematic scenes.
export function useRevealOnScroll(ref, { y = 24, stagger, selector } = {}) {
  useEffect(() => {
    if (!ref.current) return undefined;
    registerGsap();

    if (prefersReducedMotion()) {
      return undefined;
    }

    const targets = selector ? ref.current.querySelectorAll(selector) : ref.current;

    const ctx = gsap.context(() => {
      gsap.from(targets, {
        opacity: 0,
        y,
        duration: 0.7,
        ease: 'power2.out',
        stagger,
        scrollTrigger: {
          trigger: ref.current,
          start: 'top 82%',
          toggleActions: 'play none none none',
        },
      });
    });

    return () => ctx.revert();
  }, [ref, y, stagger, selector]);
}

export { ScrollTrigger };
