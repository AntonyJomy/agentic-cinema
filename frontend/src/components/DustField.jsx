import './DustField.css';

const MOTE_COUNT = 16;

const motes = Array.from({ length: MOTE_COUNT }, (_, i) => ({
  key: i,
  left: Math.round(Math.random() * 100),
  size: 2 + Math.round(Math.random() * 3),
  duration: 14 + Math.round(Math.random() * 16),
  delay: -Math.round(Math.random() * 24),
  drift: Math.round((Math.random() - 0.5) * 70),
}));

export default function DustField() {
  return (
    <div className="dust-field" aria-hidden="true">
      {motes.map((m) => (
        <span
          key={m.key}
          className="dust-mote"
          style={{
            left: `${m.left}%`,
            width: `${m.size}px`,
            height: `${m.size}px`,
            animationDuration: `${m.duration}s`,
            animationDelay: `${m.delay}s`,
            '--drift': `${m.drift}px`,
          }}
        />
      ))}
    </div>
  );
}
