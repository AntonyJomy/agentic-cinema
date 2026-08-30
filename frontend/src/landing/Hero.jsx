import { useRef, useEffect } from 'react';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import { useCursorParallax } from '../lib/useCursorParallax';
import { useMaskReveal } from '../lib/useMaskReveal';
import './Hero.css';

// Structurally matches Palomino's hero exactly: three words staggered
// diagonally (each shifted further right), full-bleed atmospheric
// background, small descriptive copy in the bottom-left corner. The
// background is an original CSS gradient/grain treatment, not a stock
// photo — Palomino's own athlete photography is theirs, not ours to reuse.
export default function Hero() {
  const heroRef = useRef(null);
  const bgRef = useRef(null);
  const word1Ref = useRef(null);
  const word2Ref = useRef(null);
  const word3Ref = useRef(null);
  const subRef = useRef(null);
  const scrollCueRef = useRef(null);

  // Ambient drift: the background glow leans gently toward the cursor.
  useCursorParallax(bgRef, { strengthX: 16, strengthY: 10 });

  // Each word slides up from behind its own mask on load, cascading
  // left-to-right — the headline arrives, it doesn't just appear. Delays
  // are offset so this starts right as the page-load wipe finishes
  // clearing (PageIntro.jsx: ~0.15s delay + 0.8s duration), rather than
  // playing underneath it.
  const revealOffset = 0.6;
  useMaskReveal(word1Ref, { immediate: true, delay: revealOffset + 0.1 });
  useMaskReveal(word2Ref, { immediate: true, delay: revealOffset + 0.22 });
  useMaskReveal(word3Ref, { immediate: true, delay: revealOffset + 0.34 });
  useMaskReveal(subRef, { immediate: true, delay: revealOffset + 0.55 });

  // Exit choreography: as the hero scrolls past, the three words and the
  // subhead each move and fade at a different rate — a "depth" relationship
  // (accent word furthest/fastest, background slowest) rather than the
  // whole block leaving as one flat unit.
  useEffect(() => {
    if (!heroRef.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const ctx = gsap.context(() => {
      gsap
        .timeline({
          scrollTrigger: {
            trigger: heroRef.current,
            start: 'top top',
            end: 'bottom top',
            scrub: true,
          },
        })
        .to(word1Ref.current, { yPercent: -14, opacity: 0.45 }, 0)
        .to(word2Ref.current, { yPercent: -26, opacity: 0.3 }, 0)
        .to(word3Ref.current, { yPercent: -40, opacity: 0.12 }, 0)
        .to(subRef.current, { yPercent: -8, opacity: 0 }, 0)
        .to(bgRef.current, { yPercent: -6 }, 0);
    }, heroRef);

    return () => ctx.revert();
  }, []);

  // Scroll-cue fades in after the headline settles, fades out once the user
  // actually starts scrolling (its job is done), and returns if they scroll
  // back to the very top. All driven by GSAP so nothing else (e.g. a CSS
  // fill-forwards animation) can end up fighting it for the same property.
  useEffect(() => {
    if (!scrollCueRef.current || prefersReducedMotion()) return undefined;
    registerGsap();

    gsap.to(scrollCueRef.current, { opacity: 1, delay: 1.4, duration: 0.6 });

    const trigger = ScrollTrigger.create({
      start: 10,
      end: 99999,
      onEnter: () => gsap.to(scrollCueRef.current, { opacity: 0, duration: 0.4 }),
      onLeaveBack: () => gsap.to(scrollCueRef.current, { opacity: 1, duration: 0.4 }),
    });

    return () => trigger.kill();
  }, []);

  return (
    <header className="hero" ref={heroRef}>
      <div className="hero-bg" ref={bgRef} />
      <div className="hero-scrim" />

      <h1 className="hero-title">
        <span className="hero-word hero-word--1" ref={word1Ref}>SCRIPTS</span>
        <span className="hero-word hero-word--2" ref={word2Ref}>INTO</span>
        <span className="hero-word hero-word--3" ref={word3Ref}>CLARITY</span>
      </h1>

      <p className="hero-sub" ref={subRef}>
        Screenplay clearance intelligence — from raw draft to a fully
        researched, evidence-backed legal review, before a single frame is shot.
      </p>

      <div className="hero-scroll-cue" ref={scrollCueRef} aria-hidden="true">
        <span className="hero-scroll-cue-label">SCROLL</span>
        <span className="hero-scroll-cue-line" />
      </div>
    </header>
  );
}
