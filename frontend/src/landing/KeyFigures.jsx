import { useRef, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './KeyFigures.css';

// Palomino's "KEY FIGURES" numbered stat grid — but a hackathon project
// has no real usage/client numbers to report, and fabricating them (e.g.
// a fake "screenplays cleared" count) would be a false claim. These three
// figures are all real and verifiable directly from the codebase.
const FIGURES = [
  { value: '6', label: 'Types of scanning' },
  { value: '7', label: 'Staged Pipeline' },
  { value: '4', label: 'Specialist Research Agents' },
];

export default function KeyFigures() {
  const ref = useRef(null);
  useRevealOnScroll(ref, { selector: '.figure-tile', stagger: 0.08 });

  // Numbers count up from zero every time the tile (re)enters the
  // viewport, in either scroll direction — not a one-time "once: true"
  // reveal. onEnter and onLeaveBack share the same replay function; each
  // call creates its own fresh {n: 0} counter object, so a re-trigger
  // always restarts the count from zero rather than resuming from
  // wherever a prior run left off. The previous run's tween is killed
  // first so two overlapping counts can't fight over the same
  // el.textContent if the user scrolls back and forth quickly.
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const valueEls = ref.current.querySelectorAll('.figure-value');
    const activeTweens = new Map();

    function replay(el, target) {
      activeTweens.get(el)?.kill();
      const counter = { n: 0 };
      const tween = gsap.to(counter, {
        n: target,
        duration: 1.1,
        ease: 'power2.out',
        onUpdate: () => { el.textContent = Math.round(counter.n); },
      });
      activeTweens.set(el, tween);
    }

    const triggers = Array.from(valueEls).map((el) => {
      const target = parseInt(el.textContent, 10);
      return ScrollTrigger.create({
        trigger: ref.current,
        start: 'top 82%',
        end: 'bottom 20%',
        onEnter: () => replay(el, target),
        onEnterBack: () => replay(el, target),
      });
    });

    return () => {
      triggers.forEach((t) => t.kill());
      activeTweens.forEach((tween) => tween.kill());
    };
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
