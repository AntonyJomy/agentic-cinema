import { useCallback, useEffect, useMemo, useState } from 'react';
import { mockRun } from '../data/mockRun';
import { RunContext } from './run-context';
import {
  getClearanceRun,
  recordEntityDecision,
  recordOverallDecision,
  runClearanceStream,
} from '../api/clearanceClient';

const RUN_STORAGE_KEY = 'scriptclear_run_id';
const useMockRun = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_RUN === 'true';

const emptyPendingScript = {
  scriptTitle: '',
  scriptText: '',
  sourceFileName: '',
};

const emptyRun = {
  run_id: '',
  script_id: '',
  script_title: '',
  created_at: '',
  updated_at: '',
  overall_status: 'pending',
  reviewed_by: null,
  reviewed_at: null,
  entities: [],
  metadata: {},
};

function persistRunId(runId) {
  try {
    if (runId) {
      sessionStorage.setItem(RUN_STORAGE_KEY, runId);
    } else {
      sessionStorage.removeItem(RUN_STORAGE_KEY);
    }
  } catch {
    // sessionStorage may be unavailable
  }
}

function readStoredRunId() {
  try {
    return sessionStorage.getItem(RUN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function RunProvider({ children }) {
  const [run, setRun] = useState(useMockRun ? mockRun : emptyRun);
  const [pendingScript, setPendingScript] = useState(emptyPendingScript);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastResponse, setLastResponse] = useState(null);
  const [pipelineEvents, setPipelineEvents] = useState([]);
  const [pipelineDuration, setPipelineDuration] = useState(null);

  const applyServerResponse = useCallback((response) => {
    if (!response?.run) return;
    setRun(response.run);
    setLastResponse(response);
    persistRunId(response.run.run_id);
  }, []);

  useEffect(() => {
    if (useMockRun) return;
    const storedId = readStoredRunId();
    if (!storedId) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await getClearanceRun(storedId);
        if (!cancelled) applyServerResponse(response);
      } catch {
        if (!cancelled) persistRunId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyServerResponse]);

  const prepareRun = useCallback(({ scriptTitle = '', scriptText = '', sourceFileName = '' }) => {
    setError(null);
    setPipelineEvents([]);
    setPipelineDuration(null);
    setLastResponse(null);
    persistRunId(null);
    setPendingScript({
      scriptTitle: scriptTitle.trim(),
      scriptText: scriptText.trim(),
      sourceFileName: sourceFileName.trim(),
    });
  }, []);

  const runClearance = useCallback(
    async ({
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
          sourceFileName: sourceFileName?.trim() || undefined,
          onProgress: (event) => {
            if (event.type === 'pipeline_complete') {
              setPipelineDuration(event.duration_seconds ?? null);
              onProgress?.(event);
              return;
            }
            setPipelineEvents((previous) => [...previous, event]);
            onProgress?.(event);
          },
        });
        applyServerResponse(response);
        return response;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Processing could not be completed.';
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [applyServerResponse]
  );

  const reloadRun = useCallback(
    async (runId = run.run_id) => {
      if (!runId) return null;
      const response = await getClearanceRun(runId);
      applyServerResponse(response);
      return response;
    },
    [applyServerResponse, run.run_id]
  );

  const submitEntityDecision = useCallback(
    async (entityId, decision, comment) => {
      if (!run.run_id) {
        throw new Error('No clearance run is loaded.');
      }
      setError(null);
      try {
        const response = await recordEntityDecision(run.run_id, entityId, {
          decision,
          comment,
        });
        applyServerResponse(response);
        return response;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'The clearance request could not be completed.';
        setError(message);
        throw err;
      }
    },
    [applyServerResponse, run.run_id]
  );

  const submitOverallDecision = useCallback(
    async (decision, comment) => {
      if (!run.run_id) {
        throw new Error('No clearance run is loaded.');
      }
      setError(null);
      try {
        const response = await recordOverallDecision(run.run_id, {
          decision,
          comment,
        });
        applyServerResponse(response);
        return response;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'The clearance request could not be completed.';
        setError(message);
        throw err;
      }
    },
    [applyServerResponse, run.run_id]
  );

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
      reloadRun,
      submitEntityDecision,
      submitOverallDecision,
      clearError,
      applyServerResponse,
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
      reloadRun,
      submitEntityDecision,
      submitOverallDecision,
      clearError,
      applyServerResponse,
    ]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}
