import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractScriptFile } from '../api/clearanceClient';
import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './UploadPage.css';

const ACCEPTED_EXTENSIONS = ['.txt', '.pdf'];

function fileExtension(name = '') {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { prepareRun, isLoading, error, clearError } = useRun();
  const fileInputRef = useRef(null);
  const [fileName, setFileName] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [scriptTitle, setScriptTitle] = useState('');
  const [scriptText, setScriptText] = useState('');
  const [localError, setLocalError] = useState(null);
  const [extractInfo, setExtractInfo] = useState(null);

  async function readFile(file) {
    if (!file) return;
    setFileName(file.name);
    setLocalError(null);
    setExtractInfo(null);
    clearError();

    const ext = fileExtension(file.name);
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setLocalError('Please upload a .txt or .pdf screenplay file.');
      setScriptText('');
      return;
    }

    setIsExtracting(true);
    try {
      if (ext === '.pdf') {
        const result = await extractScriptFile({
          file,
          scriptTitle,
        });
        setScriptText(result.script || '');
        setExtractInfo(
          result.page_count
            ? `Extracted text from ${result.page_count} PDF page(s).`
            : 'Extracted text from PDF.'
        );
        if (!scriptTitle.trim() && result.filename) {
          const base = result.filename.replace(/\.pdf$/i, '');
          if (base) setScriptTitle(base);
        }
      } else {
        const text = await file.text();
        setScriptText(text);
        setExtractInfo('Loaded text from .txt file.');
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Could not read the selected file.';
      setLocalError(message);
      setScriptText('');
      setExtractInfo(null);
    } finally {
      setIsExtracting(false);
    }
  }

  function handleFiles(files) {
    if (files && files[0]) {
      readFile(files[0]);
    }
  }

  function handleStart() {
    setLocalError(null);
    clearError();

    if (!scriptText.trim()) {
      setLocalError('Upload a .txt/.pdf screenplay or paste script text below.');
      return;
    }

    if (isLoading || isExtracting) return;

    prepareRun({
      scriptTitle,
      scriptText,
    });
    navigate('/processing');
  }

  const displayError = localError || error;
  const busy = isLoading || isExtracting;

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 1 · UPLOAD</span>
      <h1 className="page-title">Upload a script</h1>
      <p className="page-sub">
        Drop in a screenplay PDF or text file, or paste script text to start a new
        clearance run. The agent crew will extract every entity worth a legal look.
      </p>

      <div className="panel upload-panel">
        <label className="upload-field">
          <span>Script title (optional)</span>
          <input
            type="text"
            placeholder="e.g. Midnight in Sunset Park"
            value={scriptTitle}
            onChange={(e) => setScriptTitle(e.target.value)}
            disabled={busy}
          />
        </label>

        <div
          className={'dropzone' + (isDragging ? ' is-dragging' : '')}
          onClick={() => {
            if (!busy) fileInputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (!busy) handleFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.pdf,application/pdf,text/plain"
            hidden
            disabled={busy}
            onChange={(e) => handleFiles(e.target.files)}
          />
          {isExtracting ? (
            <>
              <span className="dropzone-title">Extracting text…</span>
              <span className="dropzone-hint">Reading {fileName || 'file'}</span>
            </>
          ) : fileName ? (
            <>
              <span className="dropzone-file">{fileName}</span>
              <span className="dropzone-hint">Click to choose a different file</span>
            </>
          ) : (
            <>
              <span className="dropzone-title">Drag &amp; drop your script here</span>
              <span className="dropzone-hint">PDF or TXT screenplay — or paste below</span>
            </>
          )}
        </div>

        {extractInfo && !displayError && (
          <p className="upload-extract-info">{extractInfo}</p>
        )}

        <label className="upload-field">
          <span>Or paste screenplay text</span>
          <textarea
            rows={8}
            placeholder={"INT. CAFE - DAY\n\nJohn walks into McDonald's..."}
            value={scriptText}
            disabled={busy}
            onChange={(e) => {
              setScriptText(e.target.value);
              setLocalError(null);
              clearError();
            }}
          />
        </label>

        {displayError && <p className="upload-error">{displayError}</p>}

        <button
          className="btn-primary upload-cta"
          onClick={handleStart}
          disabled={busy}
        >
          {isExtracting
            ? 'Extracting PDF…'
            : isLoading
              ? 'Analysing screenplay…'
              : 'Start clearance run'}
        </button>
      </div>
    </div>
  );
}
