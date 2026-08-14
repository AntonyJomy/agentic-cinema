/**
 * API client for the clearance backend.
 *
 * In dev, requests go through the Vite proxy (same origin) unless VITE_API_URL is set.
 */

const DEFAULT_API_URL = import.meta.env.DEV ? '' : 'http://localhost:8000';

function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL?.replace(/\/$/, '');
  if (configured !== undefined && configured !== '') {
    return configured;
  }
  return DEFAULT_API_URL;
}

function formatErrorDetail(detail) {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : JSON.stringify(item)))
      .join('; ');
  }
  return 'Clearance request failed';
}

function networkErrorMessage(error) {
  const message = error instanceof Error ? error.message : 'Network error';
  if (
    message === 'Load failed' ||
    message === 'Failed to fetch' ||
    message === 'NetworkError when attempting to fetch resource.'
  ) {
    return (
      'Could not reach the clearance backend. ' +
      'Start it with: .venv/bin/uvicorn api.main:app --reload --port 8000'
    );
  }
  return message;
}

export async function runClearance({ script, scriptTitle }) {
  let response;
  try {
    response = await fetch(`${getApiBaseUrl()}/clearance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script,
        script_title: scriptTitle || undefined,
      }),
    });
  } catch (error) {
    throw new Error(networkErrorMessage(error));
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      payload?.detail != null
        ? formatErrorDetail(payload.detail)
        : response.status === 503
          ? 'Clearance service is unavailable. Is the backend running?'
          : `Clearance request failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

/**
 * Extract screenplay text from an uploaded .txt or .pdf file.
 * @param {{ file: File, scriptTitle?: string }} params
 */
export async function extractScriptFile({ file, scriptTitle }) {
  const formData = new FormData();
  formData.append('file', file);
  if (scriptTitle?.trim()) {
    formData.append('script_title', scriptTitle.trim());
  }

  let response;
  try {
    response = await fetch(`${getApiBaseUrl()}/extract-script`, {
      method: 'POST',
      body: formData,
    });
  } catch (error) {
    throw new Error(networkErrorMessage(error));
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      payload?.detail != null
        ? formatErrorDetail(payload.detail)
        : `Could not extract text from file (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

/**
 * Run clearance with live agent progress streamed as NDJSON.
 * @param {{ script: string, scriptTitle?: string, onProgress?: (event: object) => void, signal?: AbortSignal }} params
 */
export async function runClearanceStream({ script, scriptTitle, onProgress, signal }) {
  let response;
  try {
    response = await fetch(`${getApiBaseUrl()}/clearance/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script,
        script_title: scriptTitle || undefined,
      }),
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }
    throw new Error(networkErrorMessage(error));
  }

  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const message =
      payload?.detail != null
        ? formatErrorDetail(payload.detail)
        : `Clearance request failed (${response.status})`;
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error('Clearance stream unavailable (no response body).');
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
      const event = JSON.parse(line);

      if (event.type === 'progress') {
        onProgress?.(event);
      } else if (event.type === 'complete') {
        finalResult = event.result;
        onProgress?.({
          type: 'pipeline_complete',
          duration_seconds: event.duration_seconds,
        });
      } else if (event.type === 'error') {
        throw new Error(event.detail || 'Clearance pipeline failed');
      }
    }
  }

  if (!finalResult) {
    throw new Error('Clearance stream ended without a final result.');
  }

  return finalResult;
}

export async function checkBackendHealth() {
  let response;
  try {
    response = await fetch(`${getApiBaseUrl()}/health`);
  } catch (error) {
    throw new Error(networkErrorMessage(error));
  }
  if (!response.ok) {
    throw new Error('Backend health check failed');
  }
  return response.json();
}
