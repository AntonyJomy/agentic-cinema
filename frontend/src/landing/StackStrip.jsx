import { useRef, useEffect, useState } from 'react';
import { useRevealOnScroll } from '../lib/useRevealOnScroll';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import { getScrollVelocity } from '../lib/scrollVelocityState';
import { GeminiLogo, GoogleLogo, FirebaseLogo, GoogleCloudLogo, ParallelMark } from './logos/TechLogos';
import './StackStrip.css';

// Palomino's "OUR CLIENTS" logo strip, structurally — but a hackathon
// project doesn't have real clients, so faking a client-logo row would be
// straightforwardly dishonest. This lists the actual technology the
// pipeline is genuinely built on instead, paired with each product's real
// mark (see logos/TechLogos.jsx for sourcing).
const STACK = [
  { name: 'Google Gemini', Logo: GeminiLogo },
  { name: 'Google ADK', Logo: GoogleLogo },
  { name: 'Parallel Search', Logo: ParallelMark },
  { name: 'Firebase', Logo: FirebaseLogo },
  { name: 'Cloud Firestore', Logo: GoogleCloudLogo },
];

// The loop below translates the track by exactly 1/REPEAT_COUNT of its own
// width, so copy 2 lands pixel-for-pixel where copy 1 started — seamless
// regardless of count. But that's only gap-free at any point *during* the
// loop (not just at the reset) if (REPEAT_COUNT-1) copies' worth of width
// is at least the viewport width — otherwise the trailing edge of the last
// copy runs out before the viewport does, exposing blank track just before
// each reset. One set measures roughly 900-950px; 6 copies covers up to
// ~4500px of viewport width, comfortably past 4K/ultrawide.
const REPEAT_COUNT = 6;

function StackItem({ name, Logo }) {
  return (
    <span className="stack-item">
      <Logo className="stack-item-logo" />
      <span className="stack-item-name">{name}</span>
    </span>
  );
}

export default function StackStrip() {
  const sectionRef = useRef(null);
  const trackRef = useRef(null);
  const animRef = useRef(null);
  const [reduced] = useState(() => prefersReducedMotion());
  useRevealOnScroll(sectionRef, { y: 24 });

  useEffect(() => {
    if (reduced || !trackRef.current) return undefined;
    registerGsap();

    const track = trackRef.current;
    let smoothedScale = 1;

    // Driven via the native Web Animations API rather than a GSAP tween:
    // a transform-only animation like this runs on the compositor thread,
    // so it keeps playing even if the main thread is busy (heavy scroll-
    // linked work elsewhere on the page, devtools, a recording tool eating
    // CPU) instead of stalling with it. GSAP's own ticker is only used
    // below to read scroll velocity and nudge this animation's playback
    // rate — if that read gets skipped for a few frames under load, the
    // marquee simply doesn't speed up for a moment, it never stops.
    //
    // The track renders the sequence REPEAT_COUNT times back-to-back;
    // animating exactly one copy's width (1/REPEAT_COUNT of the total) and
    // looping is what makes the wrap invisible — the next copy is already
    // sitting where the current one just vacated, so there's no snap-back
    // to see, and with enough copies (see REPEAT_COUNT's own comment)
    // there's always a full viewport of content ahead at any point in the
    // cycle, not just at the reset instant.
    const oneSetWidth = track.scrollWidth / REPEAT_COUNT;
    const pxPerSecond = window.innerWidth < 640 ? 36 : 56;
    const duration = (oneSetWidth / pxPerSecond) * 1000;
    const loopPercent = 100 / REPEAT_COUNT;

    const anim = track.animate(
      [{ transform: 'translateX(0%)' }, { transform: `translateX(-${loopPercent}%)` }],
      { duration, iterations: Infinity, easing: 'linear' }
    );
    animRef.current = anim;

    // Scroll velocity nudges the marquee's own playback rate — scrolling in
    // either direction speeds it up a little, easing back to baseline
    // (rate 1) as velocity decays. Clamped to always stay positive: the
    // movement itself must never slow to a stop or reverse, only ever vary
    // in speed. Reads off the shared Lenis-velocity singleton rather than a
    // new scroll listener.
    function tick() {
      const v = getScrollVelocity();
      const targetScale = gsap.utils.clamp(0.4, 2.5, 1 + Math.abs(v) * 0.15);
      smoothedScale += (targetScale - smoothedScale) * 0.06;
      anim.playbackRate = smoothedScale;
    }
    gsap.ticker.add(tick);

    // A backgrounded tab (switching apps, a window-resize drag, a devtools
    // breakpoint) can throttle or suspend rAF for an arbitrary stretch.
    // Explicitly pausing/resuming the animation on visibility change and
    // resetting the velocity smoothing avoids relying on the browser's own
    // throttling behavior to leave things in a sane state.
    function handleVisibility() {
      if (document.hidden) {
        anim.pause();
      } else {
        smoothedScale = 1;
        anim.playbackRate = 1;
        anim.play();
      }
    }
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      gsap.ticker.remove(tick);
      document.removeEventListener('visibilitychange', handleVisibility);
      anim.cancel();
    };
  }, [reduced]);

  const items = reduced ? STACK : Array.from({ length: REPEAT_COUNT }, () => STACK).flat();

  return (
    <section className="landing-section stack-strip" ref={sectionRef}>
      <div className="section-marker">BUILT ON</div>
      <div className={`stack-marquee${reduced ? ' stack-marquee--contained' : ''}`}>
        <div className={`stack-track${reduced ? ' stack-track--static' : ''}`} ref={trackRef}>
          {items.map((item, i) => (
            <StackItem name={item.name} Logo={item.Logo} key={`${item.name}-${i}`} />
          ))}
        </div>
      </div>
    </section>
  );
}
