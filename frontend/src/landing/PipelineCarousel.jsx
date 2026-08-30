import { useRef, useState, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './PipelineCarousel.css';

// Palomino's testimonial carousel is structurally identical to this (an
// avatar-like mark, a name, a subtitle, a "see the project" link, prev/next
// controls) — but a hackathon project has no real customers, and a fake
// named endorsement would be a false claim, not a design choice. This
// keeps the exact interaction shape and swaps its *purpose*: each slide is
// one real pipeline stage speaking for itself, not a fabricated person.
const SLIDES = [
  {
    mark: '01',
    title: 'Extraction',
    subtitle: 'Reads the full screenplay, flags every entity worth a legal look.',
  },
  {
    mark: '02',
    title: 'Grounding Check',
    subtitle: 'Deterministically filters extraction noise before any research spend.',
  },
  {
    mark: '03',
    title: 'Specialist Research',
    subtitle: 'Six agents research in parallel, each returning cited evidence.',
  },
  {
    mark: '04',
    title: 'Gatekeeper',
    subtitle: 'Nothing ships for report without an explicit human decision on record.',
  },
];

export default function PipelineCarousel() {
  const ref = useRef(null);
  const contentRef = useRef(null);
  const directionRef = useRef(1);
  const pausedRef = useRef(false);
  const [index, setIndex] = useState(0);
  useRevealOnScroll(ref);

  const slide = SLIDES[index];
  const go = (delta) => {
    directionRef.current = delta;
    setIndex((i) => (i + delta + SLIDES.length) % SLIDES.length);
  };

  // Content enters from the direction of travel — prev/next reads as motion
  // through the pipeline, not a flat content swap.
  useEffect(() => {
    if (!contentRef.current || prefersReducedMotion()) return undefined;
    registerGsap();
    gsap.fromTo(
      contentRef.current,
      { opacity: 0, x: directionRef.current * 24 },
      { opacity: 1, x: 0, duration: 0.45, ease: 'power2.out' }
    );
    return undefined;
  }, [index]);

  // Auto-advances every 5s; the interval is recreated whenever `index`
  // changes (manual or automatic), so a manual click resets the wait
  // instead of the next auto-advance landing right on top of it. Paused
  // while the cursor is over the card, and skipped entirely under
  // reduced-motion (manual prev/next still work either way).
  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    const id = setInterval(() => {
      if (!pausedRef.current) go(1);
    }, 5000);
    return () => clearInterval(id);
  }, [index]);

  return (
    <section className="landing-section pipeline-carousel" ref={ref}>
      <div
        className="carousel-card"
        onMouseEnter={() => { pausedRef.current = true; }}
        onMouseLeave={() => { pausedRef.current = false; }}
      >
        <div className="carousel-content" ref={contentRef}>
          <span className="carousel-mark">{slide.mark}</span>
          <h3 className="carousel-title">{slide.title}</h3>
          <p className="carousel-subtitle">{slide.subtitle}</p>
        </div>
        <div className="carousel-controls">
          <button type="button" aria-label="Previous stage" onClick={() => go(-1)}>←</button>
          <span className="carousel-position">{index + 1} / {SLIDES.length}</span>
          <button type="button" aria-label="Next stage" onClick={() => go(1)}>→</button>
        </div>
      </div>
    </section>
  );
}
