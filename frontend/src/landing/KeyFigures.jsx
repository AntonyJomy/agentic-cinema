import { useRef, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './KeyFigures.css';

// Palomino's "KEY FIGURES" numbered stat grid — but a hackathon project
// has no real usage/client numbers to report, and fabricating them (e.g.
// a fake "screenplays cleared" count) would be a false claim. These four
// figures are all real and verifiable directly from the codebase: the
// actual count of risk categories, entity types, specialist agents, and
// pipeline stages the system implements.
const FIGURES = [
  { value: '7', label: 'Risk categories screened' },
  { value: '9', label: 'Entity types detected' },
  { value: '6', label: 'Specialist research agents' },
  { value: '7', label: 'Pipeline stages, end to end' },
];

export default function KeyFigures() {
  const ref = useRef(null);
  useRevealOnScroll(ref, { selector: '.figure-tile', stagger: 0.08 });

  // Numbers count up from zero as the tile enters — the one moment on this
  // page where a value earns its own emphasis instead of just fading in.
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const valueEls = ref.current.querySelectorAll('.figure-value');
    const triggers = Array.from(valueEls).map((el) => {
      const target = parseInt(el.textContent, 10);
      return ScrollTrigger.create({
        trigger: ref.current,
        start: 'top 82%',
        once: true,
        onEnter: () => {
          const counter = { n: 0 };
          gsap.to(counter, {
            n: target,
            duration: 1.1,
            ease: 'power2.out',
            onUpdate: () => { el.textContent = Math.round(counter.n); },
          });
        },
      });
    });

    return () => triggers.forEach((t) => t.kill());
  }, []);

  return (
    <section className="landing-section key-figures" ref={ref}>
      <div className="section-marker">KEY FIGURES</div>
      <div className="figures-grid">
        {FIGURES.map((f, i) => (
          <div className="figure-tile" key={f.label}>
            <span className="figure-index">{i + 1}.</span>
            <span className="figure-value">{f.value}</span>
            <span className="figure-label">{f.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
