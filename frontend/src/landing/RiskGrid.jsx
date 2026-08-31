import { useRef, useEffect } from 'react';
import { useTilt } from '../lib/useTilt';
import { gsap, registerGsap, prefersReducedMotion } from '../lib/gsapConfig';
import './RiskGrid.css';

// Palomino's "SELECTED PROJECTS" mosaic, geometrically — measured directly
// off a reference screenshot (pixel coordinates, not eyeballed): row 1
// splits ~61/38 (large-left/narrow-right), row 2 splits ~36/63
// (narrow-left/large-right) — the two large cells sit on one diagonal, the
// two small cells on the other — with both rows the same height and a
// ~1.2%-of-width gutter throughout. Uses the actual risk categories the
// pipeline detects, each with its own cover image, tiled through the same
// 2x2 module (a 2-cell variant for the trailing group).
const RISK_CATEGORIES = [
  { label: 'Business & Location', image: 'business-location.jpg' },
  { label: 'Character Name Collision', image: 'character-name-collision.jpeg' },
  { label: 'Music Rights', image: 'music-rights.jpeg' },
  { label: 'Trademark & Brand', image: 'trademark-brand.jpeg' },
  { label: 'Literary Rights', image: 'literary-rights.jpeg' },
  { label: 'Defamation Risk', image: 'defamation-risk.jpeg' },
];

// `slideFrom` records which half of the mosaic each card actually sits
// in — first cell of every row is the grid's left half, second is the
// right half, regardless of whether that particular cell happens to be
// the "large" or "narrow" one — so the entrance direction below can just
// read it straight off the DOM (via data-slide-from) instead of
// re-deriving position from layout geometry at animation time.
function RiskTile({ label, image, index, className = '', slideFrom }) {
  const ref = useRef(null);
  useTilt(ref, { max: 7 });

  return (
    <div className={`risk-tile ${className}`} ref={ref} data-slide-from={slideFrom}>
      <img className="risk-tile-image" src={`/images/${image}`} alt="" />
      <div className="risk-tile-scrim" />
      <span className="risk-tile-index">{String(index + 1).padStart(2, '0')}</span>
      <span className="risk-tile-label">{label}</span>
    </div>
  );
}

// Distance each card travels in from, in px — large enough to read
// unmistakably as a directional slide rather than a small nudge, without
// being so large it looks like it's flying in from off the page.
const SLIDE_DISTANCE = 120;

export default function RiskGrid() {
  const ref = useRef(null);

  // Section-specific entrance, not the shared useRevealOnScroll (which is
  // deliberately a one-time "play none none none" reveal used sitewide) —
  // this mosaic needs to reset and replay every time it re-enters the
  // viewport, in either scroll direction, which is a genuinely different
  // trigger contract from every other section's reveal.
  useEffect(() => {
    if (!ref.current) return undefined;
    registerGsap();

    const tiles = Array.from(ref.current.querySelectorAll('.risk-tile'));

    if (prefersReducedMotion()) {
      // Plain one-time fade, no directional slide, no repeat-on-reentry —
      // matches the sitewide reduced-motion convention of "the least
      // motion that still gives new content an entrance" rather than
      // literally freezing everything mid-transform.
      gsap.set(tiles, { opacity: 0, x: 0 });
      gsap.to(tiles, {
        opacity: 1,
        duration: 0.6,
        ease: 'power2.out',
        stagger: 0.08,
        scrollTrigger: {
          trigger: ref.current,
          start: 'top 80%',
          toggleActions: 'play none none none',
        },
      });
      return undefined;
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        tiles,
        {
          opacity: 0,
          x: (_, target) => (target.dataset.slideFrom === 'right' ? SLIDE_DISTANCE : -SLIDE_DISTANCE),
        },
        {
          opacity: 1,
          x: 0,
          duration: 1.2,
          ease: 'power2.out',
          stagger: 0.08,
          overwrite: true,
          scrollTrigger: {
            trigger: ref.current,
            // ~20-30% of the section visible before it (re)triggers, in
            // either direction — loose enough that small scroll jitter
            // right at the edge doesn't cause a flurry of restarts.
            start: 'top 78%',
            end: 'bottom 25%',
            // restart on both "entering" events (scrolling down into it
            // from below, or back up into it from above) is what actually
            // gives the repeat-every-time behavior: restart snaps the
            // tween back to its fromVars (off-screen, opacity 0) before
            // playing forward again, so there's no separate "reset" step
            // needed on the two leaving events (left at "none" — the
            // tiles just stay at their last state until the next entry).
            toggleActions: 'restart none restart none',
          },
        }
      );
    }, ref);

    return () => ctx.revert();
  }, []);

  const [a, b, c, d, e, f] = RISK_CATEGORIES;

  return (
    <section className="landing-section risk-grid-section" ref={ref}>
      <div className="section-marker">WHAT WE SCREEN FOR</div>

      {/* Module 1 (cards 1-4): the reference's own 2x2 unit — row 1
          large-left/narrow-right, row 2 narrow-left/large-right. */}
      <div className="mosaic-module">
        <div className="mosaic-row mosaic-row--top">
          <RiskTile {...a} index={0} className="mosaic-cell-large" slideFrom="left" />
          <RiskTile {...b} index={1} className="mosaic-cell-narrow" slideFrom="right" />
        </div>
        <div className="mosaic-row mosaic-row--bottom">
          <RiskTile {...c} index={2} className="mosaic-cell-narrow" slideFrom="left" />
          <RiskTile {...d} index={3} className="mosaic-cell-large" slideFrom="right" />
        </div>
      </div>

      {/* Module 2 (cards 5-6): only 2 cells, so the same diagonal-emphasis
          idea becomes a single large/narrow pair (matching row 1's own
          62/38 split) rather than an even 50/50 split. */}
      <div className="mosaic-module">
        <div className="mosaic-row mosaic-row--top">
          <RiskTile {...e} index={4} className="mosaic-cell-large" slideFrom="left" />
          <RiskTile {...f} index={5} className="mosaic-cell-narrow" slideFrom="right" />
        </div>
      </div>
    </section>
  );
}
