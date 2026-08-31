import { useEffect, useRef } from 'react';
import { gsap, prefersReducedMotion } from '../lib/gsapConfig';
import { getCursor } from '../lib/cursorState';
import './CustomCursor.css';

// A small reticle that tracks the real cursor and blends via
// `mix-blend-mode: difference`, so it stays legible over both the dark page
// background and any lighter panels without any per-section hover logic.
// Skipped entirely on touch devices and under reduced-motion, since it's a
// fine-pointer-only affordance.
//
// Trail: a position-history buffer rendered as a tapered canvas stroke —
// reworked after reviewing recorded frames of palominoprod.com's actual
// cursor, which turned out to be a genuine comet-shaped stroke tracing the
// cursor's recent path (curving through direction changes, retracting to
// zero LENGTH at rest), not a straight line between two lerped points (the
// previous version here, which could only ever stretch in a straight line
// and faded via opacity rather than actually shortening).
//
// Each frame, the smoothed head position is appended to `history` (only
// when it's actually moved, so the buffer empties for real at rest rather
// than clustering at one spot) with a timestamp; points older than
// TRAIL_MAX_AGE_MS get pruned before drawing. The remaining points are
// drawn as a sequence of short strokes with width and alpha tapering from
// full at the newest (closest to the dot) to zero at the oldest — so a
// fast flick leaves many widely-spaced points (a long tapered stroke) and
// a stopped cursor has no points left within the age window at all (no
// stroke drawn, just the bare dot).
const TRAIL_MAX_AGE_MS = 200;
const TRAIL_MAX_WIDTH = 6;
const TRAIL_COLOR_RGB = '212, 162, 76'; // #D4A24C

export default function CustomCursor() {
  const dotRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (prefersReducedMotion()) return undefined;
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return undefined;

    const el = dotRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    el.classList.add('is-active');

    // scaleX/scaleY, not the 'scale' alias — quickTo's resetTo() can't
    // resolve an aliased property name (see useTilt.js for the full story).
    const scaleX = gsap.quickTo(el, 'scaleX', { duration: 0.3, ease: 'power2.out' });
    const scaleY = gsap.quickTo(el, 'scaleY', { duration: 0.3, ease: 'power2.out' });

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    let headX = 0;
    let headY = 0;
    let seeded = false;
    const history = [];

    function tick() {
      const cursor = getCursor();
      if (!seeded) {
        headX = cursor.clientX;
        headY = cursor.clientY;
        seeded = true;
      }
      // Same tight lerp as before — the reticle itself is unchanged.
      headX += (cursor.clientX - headX) * 0.35;
      headY += (cursor.clientY - headY) * 0.35;
      gsap.set(el, { x: headX, y: headY });

      const now = performance.now();
      const last = history[history.length - 1];
      if (!last || Math.hypot(headX - last.x, headY - last.y) > 0.5) {
        history.push({ x: headX, y: headY, t: now });
      }
      while (history.length && now - history[0].t > TRAIL_MAX_AGE_MS) {
        history.shift();
      }

      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      const n = history.length;
      if (n >= 2) {
        ctx.lineCap = 'round';
        for (let i = 1; i < n; i++) {
          const p0 = history[i - 1];
          const p1 = history[i];
          // 0 at the oldest (tail) point, 1 at the newest (nearest the dot)
          // — both width and alpha taper together for a comet-like fade.
          const progress = i / (n - 1);
          const width = TRAIL_MAX_WIDTH * progress;
          if (width < 0.4) continue;
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.lineWidth = width;
          ctx.strokeStyle = `rgba(${TRAIL_COLOR_RGB}, ${(0.65 * progress).toFixed(3)})`;
          ctx.shadowColor = `rgba(${TRAIL_COLOR_RGB}, 0.5)`;
          ctx.shadowBlur = 4;
          ctx.stroke();
        }
      }
    }
    gsap.ticker.add(tick);

    function onOver(e) {
      if (e.target.closest('a, button')) { scaleX(1.8); scaleY(1.8); }
    }
    function onOut(e) {
      if (e.target.closest('a, button')) { scaleX(1); scaleY(1); }
    }
    document.addEventListener('mouseover', onOver);
    document.addEventListener('mouseout', onOut);

    return () => {
      gsap.ticker.remove(tick);
      window.removeEventListener('resize', resize);
      document.removeEventListener('mouseover', onOver);
      document.removeEventListener('mouseout', onOut);
    };
  }, []);

  return (
    <>
      <canvas className="landing-cursor-canvas" ref={canvasRef} aria-hidden="true" />
      <div className="landing-cursor" ref={dotRef} aria-hidden="true">
        <span className="landing-cursor-arm landing-cursor-arm--h" />
        <span className="landing-cursor-arm landing-cursor-arm--v" />
      </div>
    </>
  );
}
