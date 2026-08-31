import { useRef, useEffect } from 'react';
import { ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import { getLenis } from '../lib/lenisState';
import './ScrollToTop.css';

// Small fixed "back to top" affordance, present across the whole page
// (mounted once in LandingPage.jsx, not scoped to any one section) —
// appears once the page has scrolled past the hero (same 80px threshold
// Nav's own solidify effect uses) and hidden again near the very top,
// where it would have nothing useful to do. Not gated behind
// prefers-reduced-motion the way most effects in this codebase are: the
// show/hide here is a scroll-position check, not a motion effect in
// itself (see the CSS for what actually is gated), and this is a
// genuinely useful navigation aid rather than decoration.
export default function ScrollToTop() {
  const buttonRef = useRef(null);

  useEffect(() => {
    if (!buttonRef.current) return undefined;
    registerGsap();

    const trigger = ScrollTrigger.create({
      start: 80,
      end: 99999,
      toggleClass: { targets: buttonRef.current, className: 'is-visible' },
    });

    return () => trigger.kill();
  }, []);

  // Routes through the shared Lenis instance (lenisState.js) rather than
  // native window.scrollTo — Lenis owns the page's actual scroll
  // position/momentum here, so an uncoordinated native scroll call would
  // just get fought/overridden on Lenis's own next animation frame.
  // Lenis is only created outside prefers-reduced-motion (see
  // useLenis.js), so falling back to native scrollTo there is also what
  // keeps this instant rather than smoothed for those users.
  function handleClick() {
    const lenis = getLenis();
    if (lenis) {
      lenis.scrollTo(0, prefersReducedMotion() ? { immediate: true } : { duration: 1.2 });
    } else {
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    }
  }

  return (
    <button
      type="button"
      className="scroll-to-top"
      ref={buttonRef}
      onClick={handleClick}
      aria-label="Back to top"
    >
      ↑
    </button>
  );
}
