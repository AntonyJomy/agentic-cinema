import { useEffect, useRef, useState } from 'react';
import { gsap, prefersReducedMotion } from '../lib/gsapConfig';
import './PageIntro.css';

// A brief solid panel that covers the viewport on first paint, then slides
// up and off-screen once — the page is uncovered rather than just appearing.
// Removed from the DOM entirely once it finishes so it can't intercept
// clicks or linger in the accessibility tree.
export default function PageIntro() {
  const panelRef = useRef(null);
  const [done, setDone] = useState(() => prefersReducedMotion());

  useEffect(() => {
    if (prefersReducedMotion() || !panelRef.current) return undefined;

    const tween = gsap.to(panelRef.current, {
      yPercent: -100,
      duration: 0.8,
      delay: 0.15,
      ease: 'expo.out',
      onComplete: () => setDone(true),
    });

    return () => tween.kill();
  }, []);

  if (done) return null;

  return <div className="page-intro" ref={panelRef} aria-hidden="true" />;
}
