import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';

let registered = false;

// Every scene imports this instead of registering plugins itself — GSAP warns
// (and wastes work) if a plugin is registered more than once across the app.
export function registerGsap() {
  if (registered) return;
  gsap.registerPlugin(ScrollTrigger, SplitText);
  registered = true;
}

export function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

// Shared vocabulary so every scene's timing feels like the same film rather
// than seven components that each invented their own pacing.
export const EASE = {
  cinematic: 'power2.inOut',
  reveal: 'power3.out',
  soft: 'sine.inOut',
};

export const DURATION = {
  sceneTransition: 1.1,
  textReveal: 0.9,
  microInteraction: 0.3,
};

export { gsap, ScrollTrigger, SplitText };
