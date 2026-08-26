import { useCallback, useMemo, useState } from 'react';
import { mockRun } from '../data/mockRun';
import { RunContext } from './run-context';
import { runClearanceStream } from '../api/clearanceClient';

const emptyPendingScript = {
  scriptTitle: '',
  scriptText: '',
  sourceFileName: '',
};

export function RunProvider({ children }) {
  const [run, setRun] = useState(mockRun);
  const [pendingScript, setPendingScript] = useState(emptyPendingScript);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastResponse, setLastResponse] = useState(null);
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineDuration, setPipelineDuration] = useState(null);

  const prepareRun = useCallback(({ scriptTitle = '', scriptText = '', sourceFileName = '' }) => {
    setError(null);
    setPipelineEvents([]);
    setPipelineDuration(null);
    setLastResponse(null);
    setPendingScript({
      scriptTitle: scriptTitle.trim(),
      scriptText: scriptText.trim(),
      sourceFileName: sourceFileName.trim(),
    });
  }, []);

  const runClearance = useCallback(async ({
    scriptText,
    scriptTitle = '',
    sourceFileName = '',
    onProgress,
  } = {}) => {
    const script = scriptText?.trim() ?? '';
    if (!script) {
      const message = 'No screenplay text provided.';
      setError(message);
      throw new Error(message);
    }

    setIsLoading(true);
    setError(null);
    setPipelineEvents([]);
    setPipelineDuration(null);

    try {
      const response = await runClearanceStream({
        script,
        scriptTitle: scriptTitle?.trim() || undefined,
        onProgress: (event) => {
          if (event.type === 'pipeline_complete') {
            setPipelineDuration(event.duration_seconds ?? null);
            onProgress?.(event);
            return;
          }

          setPipelineEvents((previous) => {
            const key = `${event.agent_id}:${event.entity_name ?? ''}`;
            const next = [...previous];
            const existingIndex = next.findIndex(
              (item) => `${item.agent_id}:${item.entity_name ?? ''}` === key
            );

            if (event.event === 'agent_start') {
              const entry = { ...event, key, startedAt: Date.now() };
              if (existingIndex >= 0) {
                next[existingIndex] = entry;
              } else {
                next.push(entry);
              }
            } else if (event.event === 'agent_complete') {
              const entry = {
                ...(existingIndex >= 0 ? next[existingIndex] : {}),
                ...event,
                key,
                completedAt: Date.now(),
              };
              if (existingIndex >= 0) {
                next[existingIndex] = entry;
              } else {
                next.push(entry);
              }
            }

            return next;
          });
          onProgress?.(event);
        },
      });

      setRun({
        ...response.run,
        metadata: {
          ...(response.run.metadata || {}),
          source_file_name:
            sourceFileName?.trim() ||
            response.run.metadata?.source_file_name ||
            undefined,
        },
      });
      setLastResponse(response);
      return response;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Clearance pipeline failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({
      run,
      pendingScript,
      isLoading,
      error,
      lastResponse,
      pipelineEvents,
      pipelineDuration,
      prepareRun,
      runClearance,
      clearError,
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
    [
      run,
      pendingScript,
      isLoading,
      error,
      lastResponse,
      pipelineEvents,
      pipelineDuration,
      prepareRun,
      runClearance,
      clearError,
    ]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
