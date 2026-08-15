export const STEPS = [
  { path: '/upload', label: 'Upload' },
  { path: '/processing', label: 'Processing' },
  { path: '/findings', label: 'Findings' },
  { path: '/review', label: 'Review' },
  { path: '/reports', label: 'Reports' },
];

export function allEntitiesReviewed(run) {
  return run.entities.every((e) => e.status !== 'flagged');
}

// Furthest step index the user is allowed to reach, derived from run state
// rather than tracked separately, so it can never drift out of sync.
export function getMaxStepIndex({ pendingScript, lastResponse, run }) {
  if (!pendingScript?.scriptText) return 0;
  if (!lastResponse) return 1;
  if (allEntitiesReviewed(run)) return 4;
  return 3;
}
