import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './UploadPage.css';

export default function UploadPage() {
  const navigate = useNavigate();
  const { prepareRun, isLoading, error, clearError } = useRun();
  const fileInputRef = useRef(null);
  const [fileName, setFileName] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [scriptTitle, setScriptTitle] = useState('');
  const [scriptText, setScriptText] = useState('');
  const [localError, setLocalError] = useState(null);

  async function readFile(file) {
    if (!file) return;
    setFileName(file.name);
    setLocalError(null);
    clearError();

    if (!file.name.toLowerCase().endsWith('.txt')) {
      setLocalError('Please upload a .txt screenplay file for now.');
      setScriptText('');
      return;
    }

    try {
      const text = await file.text();
      setScriptText(text);
    } catch {
      setLocalError('Could not read the selected file.');
      setScriptText('');
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
      setLocalError('Upload a .txt screenplay or paste script text below.');
      return;
    }

    if (isLoading) return;

    prepareRun({
      scriptTitle,
      scriptText,
    });
    navigate('/processing');
  }

  const displayError = localError || error;

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 1 · UPLOAD</span>
      <h1 className="page-title">Upload a script</h1>
      <p className="page-sub">
        Drop in a screenplay text file or paste script text to start a new clearance
        run. The agent crew will extract every entity worth a legal look.
      </p>

      <div className="panel upload-panel">
        <label className="upload-field">
          <span>Script title (optional)</span>
          <input
            type="text"
            placeholder="e.g. Midnight in Sunset Park"
            value={scriptTitle}
            onChange={(e) => setScriptTitle(e.target.value)}
          />
        </label>

        <div
          className={'dropzone' + (isDragging ? ' is-dragging' : '')}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            handleFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt"
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
          {fileName ? (
            <>
              <span className="dropzone-file">{fileName}</span>
              <span className="dropzone-hint">Click to choose a different file</span>
            </>
          ) : (
            <>
              <span className="dropzone-title">Drag &amp; drop your script here</span>
              <span className="dropzone-hint">TXT screenplay — or paste below</span>
            </>
          )}
        </div>

        <label className="upload-field">
          <span>Or paste screenplay text</span>
          <textarea
            rows={8}
            placeholder={'INT. CAFE - DAY\n\nJohn walks into McDonald\'s...'}
            value={scriptText}
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
          disabled={isLoading}
        >
          {isLoading ? 'Analysing screenplay…' : 'Start clearance run'}
        </button>
      </div>
    </div>
  );
}
