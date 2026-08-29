import { useEffect, useRef } from 'react';
import './PdfPreviewModal.css';

/**
 * Inline PDF preview.
 *
 * Renders a blob: URL in an <iframe> so the browser's native PDF viewer handles
 * paging and zoom. A blob URL is required because the report endpoint is
 * authenticated — pointing the iframe at the API path directly would send no
 * Authorization header and return 401.
 *
 * Props:
 *   title      - heading shown in the modal chrome
 *   url        - blob: object URL for the PDF, or null while loading
 *   loading    - true while the bytes are being fetched
 *   error      - message to display instead of the document
 *   reportHash   - SHA-256 recorded at sign-off, if the server provided one
 *   reportSource - 'storage' | 'regenerated'; a regenerated copy carries no
 *                  digest, so it is labelled unverifiable rather than unhashed
 *   onClose      - called on backdrop click, close button, or Escape
 *   onDownload   - optional; renders a download action in the footer
 */
export default function PdfPreviewModal({
  title,
  url,
  loading = false,
  error = null,
  reportHash = null,
  reportSource = null,
  onClose,
  onDownload,
}) {
  const closeButtonRef = useRef(null);
  const previouslyFocused = useRef(null);

  // Close on Escape, and restore focus to whatever opened the modal.
  useEffect(() => {
    previouslyFocused.current = document.activeElement;
    closeButtonRef.current?.focus();

    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose?.();
      }
    }
    document.addEventListener('keydown', onKeyDown);

    // Prevent the page behind the modal from scrolling.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [onClose]);

  return (
    <div
      className="pdf-modal-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="pdf-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`Clearance report preview: ${title}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="pdf-modal-head">
          <div className="pdf-modal-titles">
            <h2 className="pdf-modal-title">{title}</h2>
            <p className="pdf-modal-sub">Clearance report</p>
          </div>
          <button
            type="button"
            ref={closeButtonRef}
            className="pdf-modal-close"
            onClick={onClose}
            aria-label="Close preview"
          >
            Close
          </button>
        </header>

        <div className="pdf-modal-body">
          {loading ? (
            <p className="pdf-modal-status">Loading report…</p>
          ) : error ? (
            <p className="pdf-modal-status is-error" role="alert">{error}</p>
          ) : url ? (
            <iframe
              className="pdf-modal-frame"
              src={url}
              title={`Clearance report for ${title}`}
            />
          ) : (
            <p className="pdf-modal-status">No report available.</p>
          )}
        </div>

        <footer className="pdf-modal-foot">
          {reportHash ? (
            <span className="pdf-modal-hash" title={reportHash}>
              SHA-256 {reportHash.slice(0, 12)}…
            </span>
          ) : reportSource === 'regenerated' ? (
            <span className="pdf-modal-hash is-muted">
              Regenerated copy — verification unavailable
            </span>
          ) : (
            <span className="pdf-modal-hash is-muted">
              No integrity hash on record
            </span>
          )}
          {onDownload ? (
            <button type="button" className="pdf-modal-download" onClick={onDownload}>
              Download
            </button>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
