export const STEPS = [
  { path: '/upload', label: 'Upload' },
  { path: '/processing', label: 'Processing' },
  { path: '/findings', label: 'Findings' },
  { path: '/review', label: 'Review' },
  { path: '/reports', label: 'Reports' },
];

// Furthest step index the user is allowed to reach, derived from run state
// rather than tracked separately, so it can never drift out of sync.
export function getMaxStepIndex({ pendingScript, lastResponse, run }) {
  if (!pendingScript?.scriptText) return 0;
  if (!lastResponse) return 1;
  if (run.overall_status === 'approved' || run.overall_status === 'rejected') return 4;
  return 3;
}
