import { useCallback, useMemo, useState } from 'react';
import { mockRun } from '../data/mockRun';
import { RunContext } from './run-context';

const initialRun = { ...mockRun, started: false, processingDone: false };

export function RunProvider({ children }) {
  const [run, setRun] = useState(initialRun);

  // Stable identities (empty deps — all use the functional setRun form) so
  // components that depend on these in a useEffect array don't re-fire on
  // every unrelated run update. See markProcessingDone's past bug: an
  // unstable reference here re-triggered ProcessingPage's "done" effect on
  // every render, which called setRun again, which recreated this callback
  // again — an infinite loop that froze the tab right as processing finished.
  const resetRun = useCallback(
    (scriptTitle) =>
      setRun({
        ...mockRun,
        script_title: scriptTitle?.trim() || mockRun.script_title,
        overall_status: 'pending',
        reviewed_by: null,
        reviewed_at: null,
        entities: mockRun.entities.map((e) => ({ ...e, status: 'flagged' })),
        started: true,
        processingDone: false,
      }),
    []
  );

  const markProcessingDone = useCallback(
    () => setRun((prev) => (prev.processingDone ? prev : { ...prev, processingDone: true })),
    []
  );

  const updateEntityStatus = useCallback(
    (entityId, status) =>
      setRun((prev) => ({
        ...prev,
        entities: prev.entities.map((e) =>
          e.entity_id === entityId ? { ...e, status } : e
        ),
      })),
    []
  );

  const setOverallStatus = useCallback(
    (status, reviewerName) =>
      setRun((prev) => ({
        ...prev,
        overall_status: status,
        reviewed_by: reviewerName ?? prev.reviewed_by,
        reviewed_at: new Date().toISOString(),
      })),
    []
  );

  const value = useMemo(
    () => ({ run, resetRun, markProcessingDone, updateEntityStatus, setOverallStatus }),
    [run, resetRun, markProcessingDone, updateEntityStatus, setOverallStatus]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
