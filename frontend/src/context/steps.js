export const STEPS = [
  { path: '/upload', label: 'Upload' },
  { path: '/processing', label: 'Processing' },
  { path: '/findings', label: 'Findings' },
  { path: '/review', label: 'Review' },
  { path: '/reports', label: 'Reports' },
];

export function allEntitiesReviewed(run) {
  const entities = run?.entities ?? [];
  if (!entities.length) return false;
  return entities.every((e) => e.status !== 'flagged');
}

export function getMaxStepIndex({ pendingScript, lastResponse, run }) {
  const hasServerRun = Boolean(run?.run_id && lastResponse);
  if (hasServerRun) {
    return allEntitiesReviewed(run) ? 4 : 3;
  }
  if (!pendingScript?.scriptText) return 0;
  if (!lastResponse) return 1;
  return 3;
}
