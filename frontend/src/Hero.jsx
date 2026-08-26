import { useRef, useEffect, useState } from 'react';
import './Hero.css';

const TOTAL_FRAMES = 240;
const frameUrl = (n) => `/frames/ezgif-frame-${String(n).padStart(3, '0')}.jpg`;

export default function Hero() {
  const wrapperRef = useRef(null);
  const imgRef = useRef(null);
  const framesRef = useRef([]);
  const [loadedCount, setLoadedCount] = useState(0);

  // Preload every frame once on mount
  useEffect(() => {
    let cancelled = false;
    let count = 0;
    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      img.src = frameUrl(i);
      img.onload = () => {
        count += 1;
        if (!cancelled) setLoadedCount(count);
      };
      framesRef.current[i - 1] = img;
    }
    return () => { cancelled = true; };
  }, []);

  // Scroll-driven frame swap
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    function update() {
      const rect = wrapper.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const progress = Math.max(0, Math.min(1, -rect.top / total));
      const frameIndex = Math.round(progress * (TOTAL_FRAMES - 1)) + 1;
      if (imgRef.current) {
        imgRef.current.src = frameUrl(frameIndex);
      }
    }

    window.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    update();

    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  const ready = loadedCount >= TOTAL_FRAMES;

  return (
    <div className="hero-wrapper" ref={wrapperRef}>
      <section className="hero">
        <img
          ref={imgRef}
          className="hero-video"
          src={frameUrl(1)}
          alt=""
          aria-hidden="true"
        />
        {!ready && (
          <div className="hero-loading">Loading… {Math.round((loadedCount / TOTAL_FRAMES) * 100)}%</div>
        )}
        <div className="hero-scrim"></div>
        <div className="hero-content">
          <span className="eyebrow">AI AGENT CREW FOR FILM E&amp;O CLEARANCE</span>
          <h1>Clear scripts.<br />Protect stories.</h1>
          <p>
            ScriptClear AI uses an agent crew to identify legal risks, research
            real-world evidence, and deliver insurance-ready clearance reports —
            faster and with confidence.
          </p>
          <div className="cta-row">
            <a className="btn-primary" href="/upload">See it in action</a>
          </div>
          <p className="scroll-hint">Scroll to explore ↓</p>
        </div>
      </section>
    </div>
  );
}
