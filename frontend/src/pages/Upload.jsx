import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadBillingLog } from '../api/client'

/**
 * Upload page — allows user to upload billing log JSON files.
 * Supports drag-and-drop and click-to-browse.
 */
export default function Upload({ onUploadSuccess }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const fileRef = useRef(null)
  const navigate = useNavigate()

  const handleFile = async (file) => {
    if (!file) return
    setUploading(true)
    setError(null)
    setResult(null)

    try {
      const response = await uploadBillingLog(file)
      setResult(response)
      if (onUploadSuccess) {
        onUploadSuccess(response.clinic_id, response.date)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Upload Billing Log</h1>
        <p className="subtitle">
          Mehta Multi-Specialty Clinic — Kanpur, Uttar Pradesh
        </p>
      </div>

      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        id="upload-zone"
        onClick={() => fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragging(false)}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".json"
          onChange={(e) => handleFile(e.target.files[0])}
        />
        {uploading ? (
          <div className="loading-state">
            <div className="loading-spinner" />
            Processing billing log...
          </div>
        ) : (
          <>
            <h3>📄 Drop a billing log JSON file here</h3>
            <p>or click to browse — e.g. billing_log_2026-07-27.json</p>
          </>
        )}
      </div>

      {error && (
        <div className="error-banner" id="upload-error">
          ⚠️ {error}
        </div>
      )}

      {result && (
        <div className="card-panel" id="upload-result">
          <h2>✅ {result.message}</h2>
          <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)' }}>
            Clinic: <strong>{result.clinic_id}</strong> &middot;
            Date: <strong>{result.date}</strong> &middot;
            Valid: <strong>{result.valid_records}</strong> &middot;
            Rejected: <strong>{result.rejected_records}</strong>
          </p>

          {result.validation_errors?.length > 0 && (
            <div className="validation-warnings" style={{ marginTop: '16px' }}>
              <h3>⚠️ {result.rejected_records} row(s) rejected:</h3>
              <ul>
                {result.validation_errors.map((err, i) => (
                  <li key={i}>{err.message}</li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
            <button
              className="date-btn active"
              onClick={() => navigate('/reconciliation')}
            >
              View Reconciliation →
            </button>
            <button
              className="date-btn"
              onClick={() => navigate('/analytics')}
            >
              View Analytics →
            </button>
            <button
              className="date-btn"
              onClick={() => navigate('/narrative')}
            >
              AI Summary →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
