import { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useMagnetic } from '../lib/useMagnetic';
import { useMaskReveal } from '../lib/useMaskReveal';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './ClosingCta.css';

// Every particle renders as pure accent gold regardless of which word
// (gold or white) it came from — "the dust itself should read as
// uniformly gold" — with only a small per-channel jitter for texture, not
// a color tied to the source letter.
const PARTICLE_BASE_RGB = [0xD4, 0xA2, 0x4C];

function particleColor(jitter) {
  const clamp = (v) => Math.max(0, Math.min(255, v));
  const [r, g, b] = PARTICLE_BASE_RGB.map((c) => clamp(c + jitter));
  return `rgb(${r}, ${g}, ${b})`;
}

// Renders `text` offscreen using the target element's own live computed
// font (so it stays correct at whatever size .closing-title's responsive
// clamp() has resolved to), then samples its alpha channel into a sparse
// grid of particle-origin points — real glyph geometry, not manually
// placed dots, so the fragmentation genuinely traces the letter shapes
// rather than being random floating dust. Each point gets a random
// per-particle threshold (when, in 0-1 disintegration progress, it starts
// flying) and a full set of kinematic values — initial velocity, gravity,
// rotation, size — baked in once here rather than re-randomized per
// frame. That determinism is what makes the effect replay identically
// forward and backward as scroll direction reverses: position is always
// a pure function of (this particle's fixed physics, current progress),
// never of accumulated per-frame state.
//
// Threshold is biased by whether the point sits on the glyph's own edge
// (checked by probing a few pixels out in each direction in the raw,
// unsampled raster): edge points get a low threshold (they're first to
// erode), interior points a higher one — the erosion visibly starts at
// letter edges before the letterforms' cores break up.
//
// Every spatial value returned (relX/relY/velocity/gravity/size) is a
// fraction of the sampled text's own tight ink-bounding-box width, not a
// raw offscreen-canvas pixel or a fraction of this canvas's own (somewhat
// arbitrary, padded-for-descenders) height. That's what lets drawParticles
// re-anchor everything against the live element's actual center point
// using nothing but a single width ratio — sidestepping the fact that
// this offscreen canvas's padding has no reason to match the real line
// box's line-height metrics.
function sampleTextParticles(el, text) {
  const cs = getComputedStyle(el);
  const fontSize = parseFloat(cs.fontSize) || 40;
  const font = `${cs.fontWeight} ${fontSize}px ${cs.fontFamily}`;
  // .closing-title-line inherits .closing-title's letter-spacing (-0.02em)
  // — canvas text has no CSS inheritance, so it's applied explicitly, in
  // px (matching the em value against this element's own resolved size)
  // rather than trusting ctx.letterSpacing's 'em' support, which is
  // inconsistent across browsers.
  const letterSpacingPx = `${(fontSize * -0.02).toFixed(2)}px`;

  const off = document.createElement('canvas');
  const octx = off.getContext('2d', { willReadFrequently: true });
  octx.font = font;
  const metrics = octx.measureText(text);
  const w = Math.max(1, Math.ceil(metrics.width) + Math.ceil(fontSize * 0.4));
  const h = Math.max(1, Math.ceil(fontSize * 1.5));
  off.width = w;
  off.height = h;
  // Resizing a canvas resets its 2D context state, so font/letterSpacing
  // have to be re-applied after setting width/height.
  octx.font = font;
  if ('letterSpacing' in octx) octx.letterSpacing = letterSpacingPx;
  octx.fillStyle = '#fff';
  octx.textBaseline = 'alphabetic';
  octx.fillText(text, Math.ceil(fontSize * 0.2), h * 0.72);

  const { data } = octx.getImageData(0, 0, w, h);
  const alphaAt = (x, y) => {
    if (x < 0 || y < 0 || x >= w || y >= h) return 0;
    return data[(y * w + x) * 4 + 3];
  };

  let minX = w;
  let maxX = 0;
  let minY = h;
  let maxY = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (alphaAt(x, y) > 120) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX <= minX || maxY <= minY) return { points: [], inkWidth: 1 };
  const inkCenterX = (minX + maxX) / 2;
  const inkCenterY = (minY + maxY) / 2;
  const inkWidth = maxX - minX;

  // Sparser than a prior version (step 2/4, cap 6000) deliberately: real
  // flying fragments read more convincingly as fewer, more visible dust
  // motes than as a dense, barely-moving stipple — and the per-particle
  // rotation transform below (save/rotate/restore) costs more per point
  // than a plain fillRect, so a lower count keeps this affordable at scale.
  const isDesktop = window.matchMedia('(min-width: 768px)').matches;
  const step = isDesktop ? 3 : 5;
  const EDGE_PROBE = 3;
  const MAX_POINTS = 3200;
  const points = [];

  outer: for (let y = minY; y <= maxY; y += step) {
    for (let x = minX; x <= maxX; x += step) {
      if (alphaAt(x, y) <= 120) continue;
      const isEdge =
        alphaAt(x - EDGE_PROBE, y) <= 120 ||
        alphaAt(x + EDGE_PROBE, y) <= 120 ||
        alphaAt(x, y - EDGE_PROBE) <= 120 ||
        alphaAt(x, y + EDGE_PROBE) <= 120;
      const threshold = isEdge ? Math.random() * 0.3 : 0.16 + Math.random() * 0.55;
      const depth = 0.7 + Math.random() * 0.6; // >1 = travels further/slower fade ("comes forward"), <1 = the opposite ("recedes")
      // Launch angle: centered straight up (-90deg) but spread across a
      // wide arc either side, like ash lifted and scattered by a draft —
      // not a uniform fountain, and not a symmetric explosion in every
      // direction (a real minority can still launch downward-ish).
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.7;
      const speed = (0.09 + Math.random() * 0.16) * depth;
      points.push({
        relX: (x - inkCenterX) / inkWidth,
        relY: (y - inkCenterY) / inkWidth, // dividing by WIDTH for both axes (not height) keeps the shape's aspect ratio correct under a single uniform scale factor at draw time
        threshold,
        // Kinematics, all in ink-width-units per unit of this particle's
        // own local progress t (0-1): position(t) = origin + velocity*t +
        // 0.5*gravity*t^2 — a real (if simplified) launch-and-fall arc,
        // computable directly from t with no accumulated per-frame state,
        // which is what keeps the whole effect exactly reversible.
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        gravity: (0.16 + Math.random() * 0.26) * depth,
        turbPhase: Math.random() * Math.PI * 2,
        turbAmp: (0.006 + Math.random() * 0.01) * depth,
        // Rotation is the *total* amount turned by t=1 — applied as
        // rotation*localP below, so it spins up progressively rather
        // than snapping to a fixed tilt the instant the particle activates.
        rotation: (Math.random() - 0.5) * Math.PI * 3,
        sizeW: (1.4 + Math.random() * 2) * depth,
        aspect: 0.35 + Math.random() * 0.3,
        baseOpacity: 0.6 + Math.random() * 0.4,
        colorJitter: Math.round((Math.random() - 0.5) * 24),
      });
      if (points.length >= MAX_POINTS) break outer;
    }
  }
  return { points, inkWidth };
}

// Final-scroll transformation — rebuilt on the same unpinned-scrub
// mechanism as the hero (see Hero.jsx): one GSAP timeline, scrollTrigger
// scrubbed from 'top top' to 'bottom top' (this section's own natural
// scroll-past distance, no pin, no pin-spacer), every tween starting at
// timeline position 0 so text and background image move as one
// composite unit under the same scroll progress. This replaces an
// earlier pin:true version (matching a comment this file used to carry,
// claiming it already used "the same pin-and-recede mechanism as the
// hero" — stale even before this change, since Hero itself moved off
// pin:true a while back for exactly the reason described below) that
// left a well-documented dead-scroll gap afterward: pin:true's
// pinSpacing reserves (pin duration + the section's own CSS height) of
// document space, so once released, the section — still its full CSS
// height — needed to scroll past normally on top of that, during which
// the (already fully transformed) title just sat frozen while Footer
// waited its turn below. Three earlier attempts at syncing Footer's
// entry to the pin instead were each reverted after introducing a new
// bug. An unpinned scrub sidesteps the category entirely, the same way
// it already did for Hero: the section only ever costs exactly its own
// height of scroll.
//
// Particle disintegration (see the effect below): layered onto the tail
// of this same timeline rather than a separate scroll system — the
// existing button/line/title/image tweens above are untouched, so the
// section's approved choreography keeps playing exactly as before; the
// text's own opacity fade and the particle canvas are simply additional
// tweens riding the same scrub.
export default function ClosingCta() {
  const ref = useRef(null);
  const bgRef = useRef(null);
  const bgImageRef = useRef(null);
  const particleCanvasRef = useRef(null);
  const buttonRef = useRef(null);
  const titleRef = useRef(null);
  const line1Ref = useRef(null);
  const line2Ref = useRef(null);
  const { isAuthenticated } = useAuth();
  const ctaTo = isAuthenticated ? '/dashboard' : '/login';
  const ctaState = isAuthenticated ? undefined : { from: '/upload' };
  // No separate scroll-into-view reveal on the outer section here (unlike
  // most other sections) — it's also this timeline's scrollTrigger, and a
  // second, independent GSAP animation targeting the same element this
  // timeline is scrubbing would fight it for the same properties. The
  // line-level mask reveals already give it an entrance.
  useMagnetic(buttonRef, { strength: 0.3 });
  // Called per-line (not on the shared titleRef) — SplitText's mask
  // rebuilds whatever element it's given, so if it were given the shared
  // h2 it would tear down and replace these two ref'd spans entirely,
  // leaving the refs pointing at detached nodes the scroll timeline below
  // could no longer visibly affect. Matches how Hero calls it per-word.
  useMaskReveal(line1Ref);
  useMaskReveal(line2Ref, { delay: 0.1 });

  useEffect(() => {
    if (!ref.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const canvas = particleCanvasRef.current;
    const pctx = canvas.getContext('2d');

    function resizeCanvas() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      pctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resizeCanvas();

    // Sampled once up front (and again on resize, since the responsive
    // clamp() font-size changes the glyph raster) rather than every
    // scroll tick — the live per-frame cost is just repositioning
    // already-known points against each line's current
    // getBoundingClientRect(), which is what keeps the particles glued
    // to the text through its own concurrent xPercent/scale/clipPath
    // moves from the tweens above, without re-rendering text every frame.
    let line1Data = sampleTextParticles(line1Ref.current, line1Ref.current.textContent);
    let line2Data = sampleTextParticles(line2Ref.current, line2Ref.current.textContent);

    function drawParticles(dp) {
      const canvasRect = canvas.getBoundingClientRect();
      pctx.clearRect(0, 0, canvasRect.width, canvasRect.height);
      if (dp <= 0) return;

      [
        { el: line1Ref.current, data: line1Data },
        { el: line2Ref.current, data: line2Data },
      ].forEach(({ el, data }) => {
        const rect = el.getBoundingClientRect();
        // relX/relY/drift/turbulence are fractions of the sampled ink's
        // own width (see sampleTextParticles) — converting a *fraction*
        // to live pixels means multiplying by the live *width itself*
        // (rect.width), not by the width RATIO (scaleFactor below).
        // scaleFactor is for a different purpose: p.size started life as
        // an already-near-final pixel dimension, so it only needs
        // tracking against the small deviation between this element's
        // current live width and its own tight ink width — most of which
        // in practice comes from the existing scale tween on this same
        // element (rect.width already reflects that transform), so dust
        // specks shrink/grow together with whatever the text is
        // currently doing.
        const liveWidth = rect.width;
        const scaleFactor = liveWidth / data.inkWidth;
        const centerX = rect.left - canvasRect.left + rect.width / 2;
        const centerY = rect.top - canvasRect.top + rect.height / 2;
        data.points.forEach((p) => {
          const localP = Math.min(1, Math.max(0, (dp - p.threshold) / (1 - p.threshold)));
          // Not yet activated: skip entirely rather than drawing it at
          // rest on top of the letter. The real DOM text (fading via
          // opacity on the same timeline, below) already carries the
          // "still mostly solid" look on its own — a canvas-side stipple
          // sitting on top of readable, unmoved text is what previously
          // read as a sparkle/glitter overlay rather than the text itself
          // breaking apart. Only pixels actually in flight ever appear
          // here.
          if (localP <= 0) return;
          const t = localP;
          const wobble = Math.sin(t * Math.PI * 2 + p.turbPhase) * p.turbAmp * t;
          // Launch-and-fall kinematics (see sampleTextParticles): a real
          // (if simplified) arc, not a fixed drift toward one endpoint —
          // this is what makes it read as flung/falling debris rather
          // than a slow creep.
          const x = centerX + (p.relX + p.vx * t + wobble) * liveWidth;
          const y = centerY + (p.relY + p.vy * t + 0.5 * p.gravity * t * t) * liveWidth;
          // (1-t)^1.4: fades a little faster than linear as it nears full
          // flight, so particles thin out convincingly rather than
          // popping off abruptly at t===1.
          const alpha = p.baseOpacity * Math.pow(1 - t, 1.4);
          if (alpha <= 0.02) return;
          const sizeW = p.sizeW * scaleFactor;
          const sizeH = sizeW * p.aspect;
          pctx.save();
          pctx.translate(x, y);
          pctx.rotate(p.rotation * t);
          pctx.globalAlpha = alpha;
          pctx.fillStyle = particleColor(p.colorJitter);
          pctx.fillRect(-sizeW / 2, -sizeH / 2, sizeW, sizeH);
          pctx.restore();
        });
      });
      pctx.globalAlpha = 1;
    }
    drawParticles(0);

    let resizeTimer;
    function onResize() {
      resizeCanvas();
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        line1Data = sampleTextParticles(line1Ref.current, line1Ref.current.textContent);
        line2Data = sampleTextParticles(line2Ref.current, line2Ref.current.textContent);
      }, 150);
    }
    window.addEventListener('resize', onResize);

    const ctx = gsap.context(() => {
      const vh = window.innerHeight;
      const titleVertical = -vh * 0.67;

      // Image travel is a fixed fraction of the title's own travel — the
      // same "one composite camera move, not an independent background
      // drift" relationship Hero's own background image uses (see
      // Hero.jsx: bgImageRatio/bgImageTravel). Same reasoning here: the
      // image should visibly participate in the same move as the text,
      // just at a smaller magnitude, not scroll independently.
      const bgImageRatio = 0.3;
      const bgImageTravel = titleVertical * bgImageRatio;
      // Overscan: translating the image up by bgImageTravel would expose
      // this section's own background below its bottom edge unless it's
      // scaled up enough first (same problem Hero's own image has, and
      // the same fix — see Hero.jsx's scale comment for the full math).
      // Computed directly from this section's own rendered height rather
      // than hand-picked per breakpoint, since unlike Hero this section's
      // own height (112vh desktop, per ClosingCta.css) isn't a flat 100vh
      // — using the real measured height keeps the ~15% headroom correct
      // at any height this section ends up with, at any breakpoint.
      const boxHeight = ref.current.getBoundingClientRect().height;
      const bgImageScale = 1 + ((2 * Math.abs(bgImageTravel)) / boxHeight) * 1.15;

      const tl = gsap.timeline({
        defaults: { ease: 'none' },
        scrollTrigger: {
          trigger: ref.current,
          start: 'top top',
          end: 'bottom top',
          scrub: true,
        },
      });

      tl
        // The button leaves early and by fade/scale only (not x/y — those
        // stay free for useMagnetic's own hover-driven quickTo, avoiding
        // two systems fighting over the same property) — it has no place
        // in the final brand-only frame.
        .to(buttonRef.current, { opacity: 0, scale: 0.92, duration: 0.22 }, 0)
        // The two lines recompose independently rather than leaving as one
        // flat block: "LET'S CLEAR" recedes — shrinking and drifting
        // left — while "YOUR NEXT SCRIPT." grows and is progressively
        // clipped away, as if scaling past the edge of the frame.
        .to(line1Ref.current, { xPercent: -14, scale: 0.82 }, 0)
        .to(
          line2Ref.current,
          {
            xPercent: 14,
            scale: 1.22,
            clipPath: 'inset(0% 0% 60% 0%)',
          },
          0
        )
        .to(titleRef.current, { y: titleVertical }, 0)
        // Same timeline, same start position (0) as every text tween
        // above — this is what makes the image and text read as one
        // moving composition rather than text-over-a-static-photo.
        .to(bgImageRef.current, { y: bgImageTravel, scale: bgImageScale }, 0);

      // Particle disintegration rides this same timeline rather than its
      // own scroll trigger. Measured off tl's own duration-so-far (not a
      // hardcoded number) so this stays correct if any tween above is
      // ever retimed.
      //
      // Windowed early (2%-22% through the section's scroll), not late —
      // measured directly (getBoundingClientRect on the title through
      // the first 40% of scroll): the *existing*, untouched titleVertical
      // exit combined with this being a normal unpinned block (so the
      // section's own top is also continuously scrolling away underneath
      // the fixed viewport) already carries the title fully off the top
      // of the viewport by roughly 35% scroll progress — well before a
      // late window would ever become visible. Ending the disintegration
      // at ~22% keeps the whole sequence happening while the title is
      // still substantially on screen, so the user watches text actually
      // break apart rather than scrolling an already-invisible effect.
      const baseDuration = tl.duration();
      const disintegrateStart = baseDuration * 0.02;
      const disintegrateSpan = baseDuration * 0.2;
      const disintegration = { value: 0 };

      tl.fromTo(
        disintegration,
        { value: 0 },
        {
          value: 1,
          duration: disintegrateSpan,
          ease: 'none',
          onUpdate: () => drawParticles(disintegration.value),
        },
        disintegrateStart
      );
      // The letters themselves lose opacity in step with the particle
      // field growing denser — not an instant swap from solid text to
      // particles, and not a separate fade racing ahead of/behind the
      // particle motion.
      tl.to(
        [line1Ref.current, line2Ref.current],
        { opacity: 0, duration: disintegrateSpan, ease: 'none' },
        disintegrateStart
      );
    }, ref);

    return () => {
      ctx.revert();
      window.removeEventListener('resize', onResize);
      clearTimeout(resizeTimer);
    };
  }, []);

  return (
    <section className="landing-section closing-cta" ref={ref}>
      <div className="closing-bg" ref={bgRef}>
        <img className="closing-bg-image" src="/images/closing-image.png" ref={bgImageRef} alt="" />
      </div>
      <div className="closing-scrim" />
      <canvas className="closing-particles-canvas" ref={particleCanvasRef} aria-hidden="true" />
      <h2 className="closing-title" ref={titleRef}>
        <span className="closing-title-line" ref={line1Ref}>
          <span className="closing-word closing-word--gold">LET&rsquo;S</span> <span className="closing-word">CLEAR</span>
        </span>
        <br />
        <span className="closing-title-line" ref={line2Ref}>
          <span className="closing-word closing-word--gold">YOUR</span> <span className="closing-word">NEXT</span> <span className="closing-word">SCRIPT.</span>
        </span>
      </h2>
      <Link to={ctaTo} state={ctaState} className="closing-cta-button" ref={buttonRef}>
        START A CLEARANCE RUN →
      </Link>
    </section>
  );
}
