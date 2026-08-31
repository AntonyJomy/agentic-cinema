import { useRef, useEffect } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { useScrollDepth } from '../lib/useScrollDepth';
import { useMaskReveal } from '../lib/useMaskReveal';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './OurStory.css';

const PIPELINE_STAGES = [
  'Extraction',
  'Grounding check',
  'Specialist research',
  'Risk scoring',
  'Summary',
  'Legal review',
  'Gatekeeper',
];

// Fixed-duration build, not scroll-scrubbed: total time for the bar to
// fill left-to-right and all 7 checkpoints to light up in turn.
const PIPELINE_BUILD_DURATION = 3.4;

// Guards against replaying from rapid, jittery threshold crossings (e.g.
// the scroll position hovering right at the 45% boundary) — matches the
// same "don't retrigger excessively from tiny scroll jitter near the
// edge" concern the mosaic cards' entrance threshold was picked around.
const REPLAY_DEBOUNCE_MS = 400;

export default function OurStory() {
  const ref = useRef(null);
  const copyRef = useRef(null);
  const pipelineRef = useRef(null);
  const headingRef = useRef(null);
  const pipeFillRef = useRef(null);
  useRevealOnScroll(ref, { y: 32 });
  useMaskReveal(headingRef);
  useScrollDepth(copyRef, { trigger: ref, speed: -0.05 });

  // Self-playing "progress bar" build: triggered by an IntersectionObserver
  // (not ScrollTrigger's scrub) when the section is ~45% visible, then
  // runs a fixed-duration GSAP timeline to completion regardless of any
  // further scrolling. Each checkpoint lights up (dim/hollow -> filled
  // accent) as the growing bar's leading edge reaches its position and
  // then stays lit — unlike a traveling highlight, the fill and every
  // checkpoint it has passed are meant to stay visible for the rest of
  // that run, since the end state ("all 7 circles lit and the bar fully
  // filled") is also this section's plain default appearance.
  //
  // Replays every time the section (re)enters that ~45% threshold, in
  // either scroll direction — matching the same "reset and replay on
  // every entry" treatment as the mosaic cards and the sitewide reveal
  // hooks, rather than the "once per page visit" behavior this used to
  // have. IntersectionObserver doesn't distinguish which direction the
  // user scrolled to cross the threshold, so "entering from below" and
  // "re-entering from above" are already the same isIntersecting:true
  // event here — no extra logic needed for that part. The reset
  // (dim every node, zero the fill) lives inside play() itself, called
  // fresh on every entry, rather than as a separate step on exit — so a
  // run interrupted mid-build by scrolling away just keeps finishing
  // unseen in the background (harmless) and gets killed and restarted
  // from scratch the moment the section is entered again.
  //
  // The fill's progress (0-1) is written to a --pipeline-progress CSS
  // custom property rather than driven as a literal scaleX/scaleY
  // transform in JS, so the responsive CSS (see OurStory.css) can freely
  // repoint it at whichever axis the current layout actually uses —
  // horizontal on wide viewports, vertical once the timeline rotates to
  // a stacked mobile layout — without this effect needing to know about
  // that breakpoint at all.
  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const nodes = Array.from(ref.current.querySelectorAll('.story-pipeline-node'));
    const pipeFill = pipeFillRef.current;
    let timeline;
    let lastPlayedAt = 0;

    function play() {
      const now = performance.now();
      if (now - lastPlayedAt < REPLAY_DEBOUNCE_MS) return;
      lastPlayedAt = now;

      timeline?.kill();

      // Dim/hollow, not-yet-reached resting state — reapplied at the
      // start of every run (not just the first) so each replay genuinely
      // restarts from scratch rather than resuming wherever a killed
      // mid-flight run left off.
      nodes.forEach((node) => node.classList.add('is-pending'));
      pipeFill.style.setProperty('--pipeline-progress', 0);

      const progress = { value: 0 };
      timeline = gsap.timeline();
      timeline.to(
        progress,
        {
          value: 1,
          duration: PIPELINE_BUILD_DURATION,
          ease: 'power1.out',
          onUpdate: () => pipeFill.style.setProperty('--pipeline-progress', progress.value),
        },
        0
      );
      // Each node sits at the center of its own equal-width segment of
      // the row (see OurStory.css) — segment i spans [i/7, (i+1)/7] of
      // the bar, centered at (i+0.5)/7 — so checkpoints activate at
      // that same fraction of the timeline, matching the fill's
      // leading edge to each dot's actual on-screen position.
      nodes.forEach((node, i) => {
        const reachTime = ((i + 0.5) / nodes.length) * PIPELINE_BUILD_DURATION;
        timeline.call(() => node.classList.remove('is-pending'), [], reachTime);
      });
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) play();
      },
      { threshold: 0.45 }
    );
    observer.observe(ref.current);

    return () => {
      observer.disconnect();
      timeline?.kill();
    };
  }, []);

  return (
    <section className="landing-section our-story" ref={ref}>
      <div className="section-marker">OUR STORY</div>
      <div className="story-intro">
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
      </div>
      <div className="story-pipeline" ref={pipelineRef}>
        <span className="story-pipeline-label">THE PIPELINE</span>
        <div className="story-pipeline-rail">
          <span className="story-pipeline-track" aria-hidden="true" />
          <span className="story-pipeline-fill" ref={pipeFillRef} aria-hidden="true" />
          <ol className="story-pipeline-nodes">
            {PIPELINE_STAGES.map((stage, i) => (
              <li className="story-pipeline-node" key={stage}>
                <span className="story-pipeline-dot">{String(i + 1).padStart(2, '0')}</span>
                <span className="story-pipeline-node-label">{stage}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
