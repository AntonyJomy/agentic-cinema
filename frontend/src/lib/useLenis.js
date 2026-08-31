import { useEffect } from 'react';
import Lenis from 'lenis';
import { gsap, ScrollTrigger, prefersReducedMotion } from './gsapConfig';
import { setScrollVelocity } from './scrollVelocityState';
import { setLenis } from './lenisState';

// Drives smooth scroll for the whole cinematic landing page. Skipped under
// prefers-reduced-motion — native (instant) scroll is the reduced-motion
// fallback, not a slowed-down version of the same effect.
export function useLenis() {
  useEffect(() => {
    if (prefersReducedMotion()) return undefined;

    const lenis = new Lenis({
      duration: 1.1,
      smoothWheel: true,
    });
    setLenis(lenis);

    // Keep ScrollTrigger's cached measurements in sync with Lenis's virtual
    // scroll position, and drive Lenis from GSAP's own ticker so both stay
    // on the same frame clock instead of fighting over rAF.
    lenis.on('scroll', (e) => {
      ScrollTrigger.update();
      setScrollVelocity(e.velocity);
    });

    function raf(time) {
      lenis.raf(time * 1000);
    }
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
      setLenis(null);
    };
  }, []);
}
