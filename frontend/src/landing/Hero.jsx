import { useRef, useEffect } from 'react';
import { gsap, ScrollTrigger, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import { useCursorParallax } from '../lib/useCursorParallax';
import { useMaskReveal } from '../lib/useMaskReveal';
import { getCursor } from '../lib/cursorState';
import './Hero.css';

// Gooey cursor-blob "peek" (see the effect's own useEffect below for the
// full mechanism). BLOB_RADIUS is the single knob for the blob's overall
// footprint — each chain point's own radius, which at rest (all points
// converged) reads as a shape roughly 2x this value across.
const BLOB_POINT_COUNT = 6;
const BLOB_RADIUS = 85;
// Chain lerp: how fast each point catches up to the one ahead of it (point
// 0 chases the cursor, point 1 chases point 0, etc). Lower = more lag = a
// longer, more visible elastic stretch during fast movement; higher =
// tighter chain = rounder even in motion.
const BLOB_CHAIN_LERP = 0.38;
// The blob's edge is a metaball field (sum of 1/distance^2 falloff from
// each chain point, normalized by point count so a fully-converged/
// at-rest blob reproduces a single BLOB_RADIUS circle exactly) — this is
// what actually merges nearby points into one organic contour, and it's
// pure per-pixel arithmetic rather than a canvas blur+filter effect.
// FIELD_THRESHOLD is the field value that counts as "inside" the shape;
// FIELD_EDGE is the width of the antialiased transition band around it
// (in field units), so the boundary reads as a soft-but-defined edge
// rather than a hard aliased one.
//
// This replaced an earlier blur+ctx.filter version: confirmed via direct
// WebKit engine testing that `'filter' in ctx` is false there, so
// `ctx.filter = 'grayscale(100%)'` / `'blur(Npx)'` silently no-op (the
// assignment just sets an inert own-property — reads back the string,
// affects nothing) rather than throwing or falling back. That's what
// actually broke the visible reveal: the "grayscale" draw was silently
// repainting the same full-color pixels over themselves, and the "blur"
// used to merge the goo shape had no effect either. Every step below (the
// metaball field, the manual grayscale conversion) uses only
// getImageData/putImageData/drawImage, which are supported everywhere
// this ctx.filter gap isn't.
const FIELD_THRESHOLD = 1;
const FIELD_EDGE = 0.35;
// Reveal window: on-screen footprint (CSS px) around the blob's centroid
// that actually gets processed each frame — kept well above the blob's
// max on-screen spread (rest diameter ~2*BLOB_RADIUS, stretched further
// by the chain lag above) so a fast flick never clips its tail against
// this window's edge. Everything outside it is never touched, so this
// bounds the per-frame pixel work to the blob's own area instead of the
// whole hero image.
const OFFSCREEN_SIZE = 420;
// The window is actually processed (grayscale conversion + metaball
// field, both manual per-pixel loops) at this fixed, dpr-independent
// resolution, then scaled up to OFFSCREEN_SIZE by drawImage's own
// bilinear filtering — for a soft organic shape the resolution loss is
// invisible, and it keeps the per-frame pixel-loop cost constant
// regardless of screen density.
const PROCESS_SIZE = 240;
// Must match .hero-bg-image's object-position in Hero.css (center 58%) —
// used to replicate that same cover-fit crop when the canvas draws the
// same image, since ctx.drawImage() doesn't know about object-fit/
// object-position on its own.
const OBJECT_POSITION_X = 0.5;
const OBJECT_POSITION_Y = 0.58;

// Structurally matches Palomino's hero exactly: three words staggered
// diagonally (each shifted further right), full-bleed atmospheric
// background, small descriptive copy in the bottom-left corner. The
// background is an original CSS gradient/grain treatment, not a stock
// photo — Palomino's own athlete photography is theirs, not ours to reuse.
export default function Hero() {
  const heroRef = useRef(null);
  const bgRef = useRef(null);
  const bgImageRef = useRef(null);
  const bgPeekCanvasRef = useRef(null);
  const titleRef = useRef(null);
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

  // First-scroll transformation: continuous (unpinned) scroll-scrub, the
  // same mechanism this component already used below the 768px breakpoint,
  // now used at every width. Hero is an ordinary 100vh block; its own
  // internal transforms (word shear, title/sub drift, image scale+travel)
  // are scrubbed 1:1 against the natural scroll distance it takes to pass
  // the viewport (`end: 'bottom top'`) — no pin, no pin-spacer.
  //
  // This replaced an earlier pin:true version (hero pinned in place while
  // its content transformed, then released into normal flow). That
  // approach cost a structurally unavoidable ~1-viewport dead-scroll tail:
  // pin:true's default pinSpacing reserves (pin duration + hero's own CSS
  // height) of document space, so once released, hero — still a normal
  // 100vh block — needed another full viewport of scroll to actually
  // clear, during which the (fully scroll-completed) title and image just
  // sat frozen while StackStrip waited its turn. Root-caused via direct
  // ScrollTrigger/DOM measurement (pin-spacer height was a constant
  // 1750px = 750px pin duration + 1000px hero height, at every scroll
  // position). No ScrollTrigger config on the pinned element removes that
  // reserved height — pinSpacing:false does, but breaks reverse-scroll
  // here (verified: scrolling back to the top left the pin and image
  // transform permanently stuck at their end-of-scroll state) — and this
  // was the fourth attempt at preserving the pin while closing the gap,
  // matching three earlier reverted attempts (stale pre-spacer
  // measurements, overshoot-and-exit, a bad computation that mispositioned
  // Footer sitewide). An unpinned scrub sidesteps the whole category:
  // hero only ever costs exactly its own height of scroll (the same
  // physical minimum any block-level element has, pinned or not), so
  // StackStrip — its ordinary next sibling, zero gap — is already
  // entering from below as hero's remaining visible portion scrolls away,
  // with no spacer math and no pin-release edge case to get wrong on
  // reverse scroll.
  useEffect(() => {
    if (!heroRef.current || prefersReducedMotion()) return undefined;
    registerGsap();

    const ctx = gsap.context(() => {
      const vh = window.innerHeight;
      // No longer gates pinning (there isn't any) — kept only to scale the
      // animation's magnitude up on wider viewports, same as before.
      const isDesktop = window.matchMedia('(min-width: 768px)').matches;
      // The shear ratio between words (measured off the reference: roughly
      // 5 : 1 : -1.5) holds at every breakpoint there — it's the vertical
      // drift that changes, not the horizontal relationship between words.
      // This is layered on top of hero's own natural scroll-past motion
      // (it's a transform, not a reposition), so the title is fully gone
      // well before hero's own box finishes leaving the viewport — which
      // is what leaves hero's image still visibly sliding away, with
      // StackStrip entering underneath, for the remainder of hero's exit.
      const vertical = isDesktop ? -vh * 0.85 : -vh * 0.6;

      // The image's own travel is a fixed fraction of `vertical` — the
      // same number driving the title — so it reads as one composite
      // camera move rather than an independent background drift: same
      // timeline, same position (0), same scroll progress as the title.
      // It deliberately moves a *smaller* distance than the title (a
      // "same camera movement, not identical transform values"
      // relationship), because matching the title's full excursion would
      // require scaling the image far enough to lose the spotlight/figure
      // composition (see the scale comment below for the actual math).
      const bgImageRatio = 0.3;
      const bgImageTravel = vertical * bgImageRatio;
      // Overscan: translating the image up by `bgImageTravel` would expose
      // the fallback gradient below its bottom edge unless it's scaled up
      // enough first. With a centered transform-origin, scaling by `s`
      // adds (s-1)*H/2 of extra height on each side — so covering a travel
      // distance T needs s >= 1 + 2T/H (H = the image's own box height,
      // ~= vh). Solved here for T = |bgImageTravel| with ~15% headroom;
      // desktop travels further (vertical is larger there) so it needs
      // more scale than the mobile/tablet case.
      const bgImageScale = isDesktop ? 1.6 : 1.35;
      gsap
        .timeline({
          defaults: { ease: 'none' },
          scrollTrigger: {
            trigger: heroRef.current,
            start: 'top top',
            end: 'bottom top',
            scrub: true,
          },
        })
        .to(word1Ref.current, { xPercent: 50 }, 0)
        .to(word2Ref.current, { xPercent: 10 }, 0)
        .to(word3Ref.current, { xPercent: -15 }, 0)
        .to(titleRef.current, { y: vertical }, 0)
        .to(subRef.current, { y: vertical }, 0)
        // Lives on the image itself, not bgRef: bgRef already carries a
        // continuous cursor-parallax x/y (see useCursorParallax above)
        // that runs on every gsap.ticker frame regardless of scroll — a
        // second tween targeting bgRef's own y here was getting silently
        // overwritten by that per-frame parallax set immediately after
        // ScrollTrigger wrote it, which is why the background previously
        // read as static. Targeting the child image instead avoids that
        // same-property fight entirely. The blob "peek" canvas (see its own
        // effect below) reads this image's live boundingClientRect every
        // frame rather than needing its own duplicate tween, so there's
        // nothing else to keep in sync here.
        .to(bgImageRef.current, { y: bgImageTravel, scale: bgImageScale }, 0);
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

  // Gooey cursor-blob "peek": grayscale-reveals the hero background inside
  // an organic, elastic blob shape that traces the cursor's recent path.
  //
  // BLOB_POINT_COUNT circles chain-lerp toward each other (point 0 toward
  // the cursor, point 1 toward point 0, etc.), each lagging a little
  // further behind the one ahead — fast movement spreads them out along
  // the path (the blob stretches), and at rest they converge back onto
  // nearly the same spot (the blob relaxes round).
  //
  // Both the goo merge and the grayscale conversion are done as manual
  // per-pixel math (getImageData/putImageData), not ctx.filter — an
  // earlier version used ctx.filter = 'grayscale(100%)' / 'blur(Npx)',
  // which silently did nothing in WebKit (confirmed directly: `'filter'
  // in ctx` is false there, so the assignment just sets an inert own
  // property rather than affecting rendering or throwing). That's what
  // broke the visible reveal entirely — the "grayscale" draw was
  // silently repainting the same full-color pixels over themselves, so
  // moving the cursor showed no desaturation at all, just a faint edge
  // artifact from the still-functioning alpha compositing. Manual pixel
  // math has no such gap: getImageData/putImageData/drawImage are
  // supported everywhere.
  //
  // Each frame, on a small scratch canvas (colorCanvas, processed at a
  // fixed PROCESS_SIZE resolution and recentered on the chain's own
  // centroid so it only ever has to cover the blob's own on-screen
  // spread, not the whole hero):
  //  1. Draw just the cropped region of the color background image that
  //     falls under this window — cropped/scaled to replicate the real
  //     <img>'s object-fit: cover framing, read from its own live
  //     getBoundingClientRect() so it stays correct through the scroll-
  //     scrub scale/translate applied elsewhere in this component.
  //  2. Walk every pixel once: convert it to grayscale (luminance
  //     formula) AND compute its metaball field value (sum of
  //     BLOB_RADIUS^2/distance^2 from each chain point, normalized by
  //     point count so a fully-converged/at-rest blob reproduces a
  //     single BLOB_RADIUS circle exactly) in the same pass, writing the
  //     field — remapped through a narrow linear ramp around
  //     FIELD_THRESHOLD — into that pixel's alpha channel. This is what
  //     actually merges nearby points into one organic contour, entirely
  //     through arithmetic rather than any canvas blur/filter effect.
  //  3. drawImage the finished window (now grayscale RGB with the goo
  //     shape baked into its own alpha) onto the main canvas at
  //     OFFSCREEN_SIZE — no destination-in step needed since the alpha
  //     is already correct per-pixel.
  //
  // mouseenter/mouseleave on the section itself (not a bounds check every
  // frame) toggles the canvas's opacity, so leaving the hero fades the
  // whole effect out instead of leaving it stuck at its last position —
  // the chain lerp and redraw only run while the cursor is actually
  // inside.
  useEffect(() => {
    if (!heroRef.current || !bgImageRef.current || !bgPeekCanvasRef.current) return undefined;
    if (prefersReducedMotion()) return undefined;
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return undefined;

    const hero = heroRef.current;
    const colorImg = bgImageRef.current;
    const canvas = bgPeekCanvasRef.current;
    const ctx = canvas.getContext('2d');

    // Off-DOM processing canvas, fixed at PROCESS_SIZE regardless of
    // device pixel ratio — never attached to the page, just used as a
    // drawImage() source. willReadFrequently: getImageData runs on this
    // context every frame.
    const colorCanvas = document.createElement('canvas');
    colorCanvas.width = PROCESS_SIZE;
    colorCanvas.height = PROCESS_SIZE;
    const colorCtx = colorCanvas.getContext('2d', { willReadFrequently: true });

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    let active = false;
    let seeded = false;
    const points = Array.from({ length: BLOB_POINT_COUNT }, () => ({ x: 0, y: 0 }));

    function onEnter() {
      active = true;
      canvas.style.opacity = '1';
    }
    function onLeave() {
      active = false;
      canvas.style.opacity = '0';
    }
    hero.addEventListener('mouseenter', onEnter);
    hero.addEventListener('mouseleave', onLeave);

    function tick() {
      const canvasRect = canvas.getBoundingClientRect();
      if (!active) {
        ctx.clearRect(0, 0, canvasRect.width, canvasRect.height);
        return;
      }

      const cursor = getCursor();
      const targetX = cursor.clientX - canvasRect.left;
      const targetY = cursor.clientY - canvasRect.top;
      if (!seeded) {
        points.forEach((p) => { p.x = targetX; p.y = targetY; });
        seeded = true;
      }
      let leadX = targetX;
      let leadY = targetY;
      points.forEach((p) => {
        p.x += (leadX - p.x) * BLOB_CHAIN_LERP;
        p.y += (leadY - p.y) * BLOB_CHAIN_LERP;
        leadX = p.x;
        leadY = p.y;
      });

      ctx.clearRect(0, 0, canvasRect.width, canvasRect.height);

      // Guards a NaN/Infinity crop computation below if this ever ticks
      // before the image has finished loading.
      if (!colorImg.naturalWidth || !colorImg.naturalHeight) return;

      // Recenter the processing window on the chain's own centroid, same
      // as before — OFFSCREEN_SIZE only needs to cover the blob's own
      // spread, not the whole hero.
      let centroidX = 0;
      let centroidY = 0;
      points.forEach((p) => { centroidX += p.x; centroidY += p.y; });
      centroidX /= points.length;
      centroidY /= points.length;
      const bufferOriginX = centroidX - OFFSCREEN_SIZE / 2;
      const bufferOriginY = centroidY - OFFSCREEN_SIZE / 2;

      // Full cover-fit source rect for the whole <img> (drawImage knows
      // nothing about object-fit/object-position on its own — this
      // replicates Hero.css's object-fit: cover; object-position: center
      // 58% manually, same as before), used only to derive the uniform
      // source->screen scale factor below.
      const imgRect = colorImg.getBoundingClientRect();
      const naturalW = colorImg.naturalWidth;
      const naturalH = colorImg.naturalHeight;
      const imageRatio = naturalW / naturalH;
      const destRatio = imgRect.width / imgRect.height;
      let sx;
      let sy;
      let sWidth;
      let sHeight;
      if (imageRatio > destRatio) {
        sHeight = naturalH;
        sWidth = sHeight * destRatio;
        sx = (naturalW - sWidth) * OBJECT_POSITION_X;
        sy = 0;
      } else {
        sWidth = naturalW;
        sHeight = sWidth / destRatio;
        sx = 0;
        sy = (naturalH - sHeight) * OBJECT_POSITION_Y;
      }
      const coverScale = imgRect.width / sWidth;

      // Crop just the sub-rect of the natural image under our small
      // processing window, in the same source-pixel space, then draw it
      // straight to PROCESS_SIZE (no filter — full color, cropped only).
      const windowLeftClient = canvasRect.left + bufferOriginX;
      const windowTopClient = canvasRect.top + bufferOriginY;
      const srcWindowX = sx + (windowLeftClient - imgRect.left) / coverScale;
      const srcWindowY = sy + (windowTopClient - imgRect.top) / coverScale;
      const srcWindowSize = OFFSCREEN_SIZE / coverScale;

      colorCtx.clearRect(0, 0, PROCESS_SIZE, PROCESS_SIZE);
      colorCtx.drawImage(
        colorImg,
        srcWindowX,
        srcWindowY,
        srcWindowSize,
        srcWindowSize,
        0,
        0,
        PROCESS_SIZE,
        PROCESS_SIZE
      );

      // One pass over every pixel: manual grayscale conversion + metaball
      // field alpha, both baked directly into this buffer's own pixels.
      const imageData = colorCtx.getImageData(0, 0, PROCESS_SIZE, PROCESS_SIZE);
      const data = imageData.data;
      const processScale = PROCESS_SIZE / OFFSCREEN_SIZE;
      const fieldRadius = BLOB_RADIUS * processScale;
      const r2 = fieldRadius * fieldRadius;
      const bufPoints = points.map((p) => ({
        x: (p.x - bufferOriginX) * processScale,
        y: (p.y - bufferOriginY) * processScale,
      }));
      const n = bufPoints.length;
      const lowEdge = FIELD_THRESHOLD - FIELD_EDGE;

      for (let py = 0; py < PROCESS_SIZE; py++) {
        for (let px = 0; px < PROCESS_SIZE; px++) {
          const idx = (py * PROCESS_SIZE + px) * 4;

          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];
          const gray = 0.299 * r + 0.587 * g + 0.114 * b;
          data[idx] = gray;
          data[idx + 1] = gray;
          data[idx + 2] = gray;

          let field = 0;
          for (let i = 0; i < n; i++) {
            const dx = px - bufPoints[i].x;
            const dy = py - bufPoints[i].y;
            field += r2 / (dx * dx + dy * dy + 1);
          }
          field /= n;

          let a = (field - lowEdge) / (2 * FIELD_EDGE);
          if (a < 0) a = 0;
          else if (a > 1) a = 1;
          data[idx + 3] = a * 255;
        }
      }
      colorCtx.putImageData(imageData, 0, 0);

      ctx.drawImage(colorCanvas, bufferOriginX, bufferOriginY, OFFSCREEN_SIZE, OFFSCREEN_SIZE);
    }
    gsap.ticker.add(tick);

    return () => {
      gsap.ticker.remove(tick);
      window.removeEventListener('resize', resize);
      hero.removeEventListener('mouseenter', onEnter);
      hero.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  return (
    <header className="hero" ref={heroRef}>
      <div className="hero-bg" ref={bgRef}>
        <img className="hero-bg-image" src="/images/title-bg.png" ref={bgImageRef} alt="" />
        <canvas className="hero-bg-peek-canvas" ref={bgPeekCanvasRef} aria-hidden="true" />
      </div>
      <div className="hero-scrim" />

      <h1 className="hero-title" ref={titleRef}>
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
