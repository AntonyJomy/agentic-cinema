import { useEffect } from 'react';
import { gsap, SplitText, registerGsap, prefersReducedMotion } from './gsapConfig';

// Splits a heading into lines, each auto-wrapped in its own overflow-hidden
// mask (SplitText's `mask` option), then slides each line up from behind
// that mask — text arrives from behind itself rather than fading/sliding
// as one flat block. `immediate: true` plays once on mount (for
// above-the-fold headings, which aren't a "scroll into view" reveal to
// begin with); everything else is gated by scroll position and replays
// every time it's (re)entered, in either direction — `restart none
// restart none` snaps the tween back behind its mask on each entry
// (from below or re-entering from above) rather than revealing once and
// staying revealed.
export function useMaskReveal(ref, {
  type = 'lines',
  start = 'top 85%',
  end = 'bottom 15%',
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
      overwrite: true,
      scrollTrigger: immediate ? undefined : {
        trigger: ref.current,
        start,
        end,
        toggleActions: 'restart none restart none',
      },
    });

    return () => {
      tween.scrollTrigger && tween.scrollTrigger.kill();
      tween.kill();
      split.revert();
    };
  }, [ref, type, start, end, immediate, delay, stagger]);
}
