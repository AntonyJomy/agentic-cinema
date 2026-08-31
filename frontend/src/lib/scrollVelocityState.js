// Shared scroll-velocity singleton, fed by the single Lenis instance
// (useLenis.js) rather than having every consumer track scroll deltas
// itself. Positive = scrolling down, negative = scrolling up.
const state = { velocity: 0 };

export function setScrollVelocity(v) {
  state.velocity = v;
}

export function getScrollVelocity() {
  return state.velocity;
}
