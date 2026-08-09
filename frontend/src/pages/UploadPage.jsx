import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRun } from '../context/useRun';
import '../styles/shared.css';
import './UploadPage.css';

export default function UploadPage() {
  const navigate = useNavigate();
  const { resetRun } = useRun();
  const fileInputRef = useRef(null);
  const [fileName, setFileName] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [scriptTitle, setScriptTitle] = useState('');

  function handleFiles(files) {
    if (files && files[0]) setFileName(files[0].name);
  }

  function handleStart() {
    resetRun(scriptTitle);
    navigate('/processing');
  }

  return (
    <div className="app-page">
      <span className="page-eyebrow">STEP 1 · UPLOAD</span>
      <h1 className="page-title">Upload a script</h1>
      <p className="page-sub">
        Drop in a screenplay PDF or script text file to start a new clearance
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
            accept=".pdf,.txt,.fdx"
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
              <span className="dropzone-hint">PDF, TXT or Final Draft — or click to browse</span>
            </>
          )}
        </div>

        <button className="btn-primary upload-cta" onClick={handleStart}>
          Start clearance run
        </button>
      </div>
    </div>
  );
}
