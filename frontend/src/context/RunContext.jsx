import { useMemo, useState } from 'react';
import { mockRun } from '../data/mockRun';
import { RunContext } from './run-context';

export function RunProvider({ children }) {
  const [run, setRun] = useState(mockRun);

  const value = useMemo(
    () => ({
      run,
      resetRun: (scriptTitle) =>
        setRun({
          ...mockRun,
          script_title: scriptTitle?.trim() || mockRun.script_title,
          overall_status: 'pending',
          reviewed_by: null,
          reviewed_at: null,
          entities: mockRun.entities.map((e) => ({ ...e, status: 'flagged' })),
        }),
      updateEntityStatus: (entityId, status) =>
        setRun((prev) => ({
          ...prev,
          entities: prev.entities.map((e) =>
            e.entity_id === entityId ? { ...e, status } : e
          ),
        })),
      setOverallStatus: (status, reviewerName) =>
        setRun((prev) => ({
          ...prev,
          overall_status: status,
          reviewed_by: reviewerName ?? prev.reviewed_by,
          reviewed_at: new Date().toISOString(),
        })),
    }),
    [run]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
