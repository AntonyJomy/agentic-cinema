import { useEffect } from 'react';
import { gsap, SplitText, registerGsap, prefersReducedMotion } from './gsapConfig';

// Splits a heading into lines, each auto-wrapped in its own overflow-hidden
// mask (SplitText's `mask` option), then slides each line up from behind
// that mask — text arrives from behind itself rather than fading/sliding
// as one flat block. `immediate: true` plays on mount (for above-the-fold
// headings); otherwise it's gated by scroll position like everything else.
export function useMaskReveal(ref, {
  type = 'lines',
  start = 'top 85%',
  immediate = false,
  delay = 0,
  stagger = 0.06,
} = {}) {
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const split = SplitText.create(ref.current, { type, mask: type });
    const targets = split[type];

    const tween = gsap.from(targets, {
      yPercent: 110,
      duration: 0.9,
      ease: 'power3.out',
      stagger,
      delay,
      scrollTrigger: immediate ? undefined : {
        trigger: ref.current,
        start,
        toggleActions: 'play none none none',
      },
    });

    return () => {
      tween.scrollTrigger && tween.scrollTrigger.kill();
      tween.kill();
      split.revert();
    };
  }, [ref, type, start, immediate, delay, stagger]);
}
