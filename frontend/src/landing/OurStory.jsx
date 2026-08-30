import { useRef, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useScrollDepth } from '../lib/useScrollDepth';
import { useMaskReveal } from '../lib/useMaskReveal';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './OurStory.css';

export default function OurStory() {
  const ref = useRef(null);
  const copyRef = useRef(null);
  const panelRef = useRef(null);
  const headingRef = useRef(null);
  useRevealOnScroll(ref, { y: 32 });
  useMaskReveal(headingRef);

  // Copy and the pipeline panel drift at different rates — a paired
  // relationship, not two independent effects.
  useScrollDepth(copyRef, { trigger: ref, speed: -0.05 });
  useScrollDepth(panelRef, { trigger: ref, speed: 0.08 });

  // Scroll position through the section doubles as pipeline progress: the
  // step list lights up in order as the reader moves through it.
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const steps = ref.current.querySelectorAll('.story-steps li');
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: ref.current,
        start: 'top center',
        end: 'bottom center',
        scrub: true,
        onUpdate: (self) => {
          const active = Math.min(steps.length - 1, Math.floor(self.progress * steps.length));
          steps.forEach((step, i) => step.classList.toggle('is-active', i === active));
        },
      });
    }, ref);

    return () => ctx.revert();
  }, []);

  return (
    <section className="landing-section our-story" ref={ref}>
      <div className="section-marker">OUR STORY</div>
      <div className="story-grid">
        <div className="story-copy" ref={copyRef}>
          <h2 className="story-heading" ref={headingRef}>
            Built to catch what a first read misses.
          </h2>
          <p className="story-paragraph">
            ScriptClear AI started as a straightforward question: before a
            screenplay goes into production, who actually checks every
            named business, character, song, and address for legal
            exposure? Usually a legal team, working line by line, well
            after the script is locked.
          </p>
          <p className="story-paragraph">
            We built an agent pipeline that does that first pass —
            extraction, grounding, specialist research, and risk scoring —
            in minutes, with real citations attached to every flagged
            entity, so a human reviewer starts from evidence instead of a
            blank page.
          </p>
        </div>
        <div className="story-panel" ref={panelRef}>
          <span className="story-panel-label">THE PIPELINE</span>
          <ol className="story-steps">
            <li>Extraction</li>
            <li>Grounding check</li>
            <li>Specialist research</li>
            <li>Risk scoring</li>
            <li>Summary</li>
            <li>Legal review</li>
            <li>Gatekeeper</li>
          </ol>
        </div>
      </div>
    </section>
  );
}
