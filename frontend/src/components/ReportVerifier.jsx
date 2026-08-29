import { useId, useRef, useState } from 'react';
import {
  VERIFY_STATE,
  isHashingSupported,
  verifyReportFile,
} from '../lib/reportIntegrity';
import './ReportVerifier.css';

function formatSignOffDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return null;
  }
}

/**
 * Tamper-Evident Verification.
 *
 * The user drops a report PDF they already hold; it is hashed locally and
 * compared to the digest recorded when the run was signed off. The file is never
 * uploaded — there is no endpoint behind this, only crypto.subtle in the page.
 *
 * Props:
 *   expectedHash - report_hash from the run record, or null if none was stored
 *   signedOffAt  - ISO timestamp shown on a successful match
 */
export default function ReportVerifier({ expectedHash = null, signedOffAt = null }) {
  const inputId = useId();
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [filename, setFilename] = useState(null);

  const supported = isHashingSupported();

  async function handleFile(file) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setFilename(file.name);
    try {
      setResult(await verifyReportFile(file, expectedHash));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read that file.');
    } finally {
      setBusy(false);
    }
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    handleFile(event.dataTransfer?.files?.[0]);
  }

  function onDragOver(event) {
    event.preventDefault();
    setDragging(true);
  }

  function reset() {
    setResult(null);
    setError(null);
    setFilename(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <section className="verifier no-print" aria-labelledby={`${inputId}-heading`}>
      <div className="verifier-head">
        <h3 id={`${inputId}-heading`} className="verifier-title">
          Tamper-Evident Verification
        </h3>
        <p className="verifier-sub">
          Drop a clearance report to check it against the digest recorded at
          sign-off. The file is hashed in your browser and never uploaded.
        </p>
      </div>

      {!supported ? (
        <p className="verifier-status is-neutral" role="status">
          Verification needs a secure context (https, or localhost). Open this page
          over https to enable it.
        </p>
      ) : (
        <>
          <div
            className={`verifier-drop${dragging ? ' is-dragging' : ''}${busy ? ' is-busy' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={() => setDragging(false)}
          >
            <input
              id={inputId}
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="verifier-input"
              onChange={(event) => handleFile(event.target.files?.[0])}
              disabled={busy}
            />
            <label htmlFor={inputId} className="verifier-label">
              <span className="verifier-label-strong">
                {busy ? 'Hashing…' : 'Verify a report'}
              </span>
              <span className="verifier-label-hint">
                Drop the PDF here, or choose a file
              </span>
            </label>
          </div>

          {filename ? (
            <p className="verifier-filename" title={filename}>
              Checked: {filename}
            </p>
          ) : null}

          {error ? (
            <p className="verifier-status is-mismatch" role="alert">{error}</p>
          ) : null}

          {result ? <VerifierResult result={result} signedOffAt={signedOffAt} onReset={reset} /> : null}
        </>
      )}
    </section>
  );
}

function VerifierResult({ result, signedOffAt, onReset }) {
  const { state, actualHash, expectedHash, isPdf } = result;
  const signedOn = formatSignOffDate(signedOffAt);

  let toneClass = 'is-neutral';
  let heading = 'No reference hash on record';
  let detail = 'There is no stored digest for this run, so this file cannot be verified.';

  if (state === VERIFY_STATE.VERIFIED) {
    toneClass = 'is-verified';
    heading = 'Verified';
    detail = signedOn
      ? `This is the genuine report as signed off on ${signedOn}.`
      : 'This is the genuine report as signed off.';
  } else if (state === VERIFY_STATE.MISMATCH) {
    toneClass = 'is-mismatch';
    heading = 'Mismatch';
    detail =
      'This file does not match the signed-off report — it may have been altered or is a different version.';
  }

  return (
    <div className={`verifier-result ${toneClass}`} role="status" aria-live="polite">
      <div className="verifier-result-head">
        <span className="verifier-badge">{heading}</span>
        <button type="button" className="verifier-reset" onClick={onReset}>
          Check another
        </button>
      </div>
      <p className="verifier-detail">{detail}</p>

      {state === VERIFY_STATE.MISMATCH && !isPdf ? (
        <p className="verifier-note">
          This file does not begin with a PDF signature, so it may not be a
          clearance report at all.
        </p>
      ) : null}

      <dl className="verifier-hashes">
        <div>
          <dt>This file</dt>
          <dd title={actualHash}>{actualHash}</dd>
        </div>
        <div>
          <dt>On record</dt>
          <dd title={expectedHash || ''}>{expectedHash || '— none —'}</dd>
        </div>
      </dl>

      <p className="verifier-footnote">
        SHA-256 comparison confirms the file is byte-identical to the artifact
        hashed at sign-off. It does not, on its own, prove who produced it.
      </p>
    </div>
  );
}
