/**
 * API client for the clearance backend.
 *
 * One central base URL:
 * - Development: VITE_API_URL, or '' to use the Vite proxy
 * - Production: VITE_API_URL is required (no localhost fallback)
 */

const GENERIC_CONNECT = 'Unable to connect to the clearance service.';
const GENERIC_FAILED = 'The clearance request could not be completed.';
const GENERIC_PROCESS = 'An error occurred while analysing the script.';

function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL?.replace(/\/$/, '');
  if (import.meta.env.DEV) {
    if (configured !== undefined && configured !== '') {
      return configured;
    }
    return '';
  }
  if (!configured) {
    throw new Error('VITE_API_URL is required in production builds.');
  }
  return configured;
}

function apiUrl(path) {
  const base = getApiBaseUrl();
  return `${base}${path}`;
}

async function authHeaders(extra = {}, { forceRefresh = false } = {}) {
  // Lazy import keeps the API client usable in tests without Firebase env.
  const { getIdToken } = await import('../auth/firebase');
  const token = await getIdToken(forceRefresh);
  const headers = { ...extra };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function formatErrorDetail(detail) {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : null))
      .filter(Boolean);
    if (messages.length) return messages.join('; ');
  }
  return GENERIC_FAILED;
}

function networkErrorMessage(error) {
  if (error instanceof Error && error.name === 'AbortError') {
    return error;
  }
  return new Error(GENERIC_CONNECT);
}

function statusMessage(status, fallback) {
  if (status === 401) return 'Sign in required to use the clearance service.';
  if (status === 403) return 'You do not have permission for this action.';
  if (status === 413) return 'The uploaded file is too large.';
  if (status === 429) return 'Too many requests. Please wait and try again.';
  if (status === 503) return 'The clearance service is temporarily unavailable.';
  if (status >= 500) return fallback || GENERIC_PROCESS;
  return fallback || GENERIC_FAILED;
}

async function readJsonSafe(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function parseError(response, fallback) {
  const payload = await readJsonSafe(response);
  if (payload?.detail != null) {
    const formatted = formatErrorDetail(payload.detail);
    if (response.status >= 500) {
      return statusMessage(response.status, fallback);
    }
    return formatted;
  }
  return statusMessage(response.status, fallback);
}

export async function runClearance({ script, scriptTitle, sourceFileName, signal }) {
  let response;
  try {
    response = await fetch(apiUrl('/clearance'), {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        script,
        script_title: scriptTitle || undefined,
        source_file_name: sourceFileName || undefined,
      }),
      signal,
    });
  } catch (error) {
    throw networkErrorMessage(error);
  }

  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_PROCESS));
  }

  const payload = await readJsonSafe(response);
  if (!payload?.run?.run_id) {
    throw new Error(GENERIC_FAILED);
  }
  return payload;
}

export async function extractScriptFile({ file, scriptTitle, signal }) {
  const formData = new FormData();
  formData.append('file', file);
  if (scriptTitle?.trim()) {
    formData.append('script_title', scriptTitle.trim());
  }

  let response;
  try {
    response = await fetch(apiUrl('/extract-script'), {
      method: 'POST',
      headers: await authHeaders(),
      body: formData,
      signal,
    });
  } catch (error) {
    throw networkErrorMessage(error);
  }

  if (!response.ok) {
    throw new Error(await parseError(response, 'Could not extract text from this file.'));
  }

  const payload = await readJsonSafe(response);
  if (!payload || typeof payload.script !== 'string') {
    throw new Error('Could not extract text from this file.');
  }
  return payload;
}

export async function runClearanceStream({
  script,
  scriptTitle,
  sourceFileName,
  onProgress,
  signal,
}) {
  let response;
  try {
    response = await fetch(apiUrl('/clearance/stream'), {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        script,
        script_title: scriptTitle || undefined,
        source_file_name: sourceFileName || undefined,
      }),
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }
    throw new Error(GENERIC_CONNECT);
  }

  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_PROCESS));
  }

  if (!response.body) {
    throw new Error('Processing could not be completed.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.trim()) continue;
      let event;
      try {
        event = JSON.parse(line);
      } catch {
        throw new Error('Processing could not be completed.');
      }

      if (event.type === 'progress') {
        onProgress?.(event);
      } else if (event.type === 'complete') {
        finalResult = event.result;
        onProgress?.({
          type: 'pipeline_complete',
          duration_seconds: event.duration_seconds,
        });
      } else if (event.type === 'error') {
        throw new Error(event.detail || GENERIC_PROCESS);
      }
    }
  }

  if (!finalResult?.run?.run_id) {
    throw new Error('Processing could not be completed.');
  }

  return finalResult;
}

export async function listClearanceRuns({ signal } = {}) {
  let response;
  try {
    // Force-refresh so a stale/missing cached token does not produce an empty
    // or 401 dashboard right after Google sign-in on Cloud Run.
    response = await fetch(apiUrl('/clearance'), {
      method: 'GET',
      headers: await authHeaders({}, { forceRefresh: true }),
      signal,
    });
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_FAILED));
  }
  const payload = await readJsonSafe(response);
  if (!payload || !Array.isArray(payload.runs)) {
    throw new Error(GENERIC_FAILED);
  }
  return payload.runs;
}

/**
 * Fetch the clearance report PDF for a run.
 *
 * The endpoint requires an Authorization header, so the bytes must be fetched
 * here rather than pointed at directly from an <iframe> or <a href>. Returns the
 * validated blob plus the server-suggested filename and the SHA-256 recorded at
 * sign-off, so callers can download it, preview it, or verify it.
 */
async function fetchClearancePdf(runId, { signal } = {}) {
  let response;
  try {
    response = await fetch(
      apiUrl(`/clearance/${encodeURIComponent(runId)}/pdf`),
      {
        method: 'GET',
        headers: await authHeaders(),
        signal,
      }
    );
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_FAILED));
  }

  const blob = await response.blob();
  if (!blob || blob.size < 5) {
    throw new Error('The PDF was empty.');
  }
  // Guard against error JSON being surfaced as a ".pdf"
  const head = await blob.slice(0, 5).text();
  if (head !== '%PDF-') {
    throw new Error('The server did not return a valid PDF.');
  }

  const disposition = response.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="([^"]+)"/i);

  return {
    blob,
    suggestedFilename: match?.[1] || 'clearance_report.pdf',
    // Present only when the stored artifact was served. A regenerated copy
    // deliberately carries no digest, because rebuilding the PDF changes its
    // bytes and comparing against the sign-off hash would false-flag a mismatch.
    reportHash: response.headers.get('X-Report-SHA256') || null,
    // 'storage' | 'regenerated' | null
    reportSource: response.headers.get('X-Report-Source') || null,
  };
}

/**
 * Load a report as an object URL for inline preview.
 *
 * The caller owns the returned url and MUST call URL.revokeObjectURL on it when
 * the preview closes, otherwise the blob is retained for the page's lifetime.
 */
export async function openClearancePdfPreview(runId, { signal } = {}) {
  const { blob, suggestedFilename, reportHash, reportSource } =
    await fetchClearancePdf(runId, { signal });
  return {
    url: URL.createObjectURL(blob),
    suggestedFilename,
    reportHash,
    reportSource,
    sizeBytes: blob.size,
  };
}

export async function downloadClearancePdf(runId, { signal, filename } = {}) {
  const { blob, suggestedFilename } = await fetchClearancePdf(runId, { signal });
  const downloadName = filename || suggestedFilename;

  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = downloadName;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export async function getClearanceRun(runId, { signal } = {}) {
  let response;
  try {
    response = await fetch(apiUrl(`/clearance/${encodeURIComponent(runId)}`), {
      method: 'GET',
      headers: await authHeaders(),
      signal,
    });
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_FAILED));
  }
  const payload = await readJsonSafe(response);
  if (!payload?.run?.run_id) {
    throw new Error(GENERIC_FAILED);
  }
  return payload;
}

export async function recordEntityDecision(runId, entityId, { decision, comment, signal } = {}) {
  let response;
  try {
    response = await fetch(
      apiUrl(
        `/clearance/${encodeURIComponent(runId)}/entities/${encodeURIComponent(entityId)}/decision`
      ),
      {
        method: 'POST',
        headers: await authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          decision,
          comment: comment || undefined,
        }),
        signal,
      }
    );
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_FAILED));
  }
  const payload = await readJsonSafe(response);
  if (!payload?.run?.run_id) {
    throw new Error(GENERIC_FAILED);
  }
  return payload;
}

export async function recordOverallDecision(runId, { decision, comment, signal } = {}) {
  let response;
  try {
    response = await fetch(apiUrl(`/clearance/${encodeURIComponent(runId)}/decision`), {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        decision,
        comment: comment || undefined,
      }),
      signal,
    });
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error(await parseError(response, GENERIC_FAILED));
  }
  const payload = await readJsonSafe(response);
  if (!payload?.run?.run_id) {
    throw new Error(GENERIC_FAILED);
  }
  return payload;
}

export async function checkBackendHealth() {
  let response;
  try {
    response = await fetch(apiUrl('/health'));
  } catch (error) {
    throw networkErrorMessage(error);
  }
  if (!response.ok) {
    throw new Error('Backend health check failed');
  }
  return response.json();
}
