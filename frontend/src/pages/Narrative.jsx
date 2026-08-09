import { useState, useEffect } from 'react'
import { getNarrative } from '../api/client'

/**
 * Screen 3: AI Narrative Summary
 * Matches the assignment screenshot exactly:
 * - Left: Green-tinted narrative card with WhatsApp-style summary
 * - Right: Traced Figures panel mapping numbers to report fields
 * - "AI SUGGESTED" badge + "SUCCESS" status badge
 */
export default function Narrative({ clinicId, date }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!clinicId || !date) return

    setLoading(true)
    setError(null)
    getNarrative(clinicId, date)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [clinicId, date])

  if (!clinicId || !date) {
    return (
      <div className="empty-state">
        <div className="emoji">🤖</div>
        <h2>No Data Available</h2>
        <p>Upload a billing log to generate the AI narrative summary.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        Generating AI narrative summary...
      </div>
    )
  }

  if (error) {
    return <div className="error-banner">⚠️ {error}</div>
  }

  if (!data) return null

  return (
    <div id="narrative-page">
      <div className="page-header">
        <span className="ai-badge">AI SUGGESTED</span>
        <h1>AI Narrative Summary</h1>
        <p className="subtitle">
          Generated from today's reconciliation — Mehta Multi-Specialty Clinic
        </p>
        <span className="ai-badge corner">AI SUGGESTED</span>
      </div>

      <div className="narrative-layout">
        {/* Left: Narrative Card */}
        <div className="narrative-card" id="narrative-content">
          <div className="send-to">
            Sent to: Dr. Anand Mehta · WhatsApp
          </div>
          <div className="narrative-text">
            {data.narrative.split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
          <span className={`success-badge ${data.status === 'success' ? '' : 'fallback'}`}>
            {data.status === 'success' ? 'SUCCESS' : 'FALLBACK'}
          </span>
        </div>

        {/* Right: Traced Figures */}
        <div className="traced-panel" id="traced-figures">
          <h2>Traced Figures</h2>
          <p className="traced-description">
            Every number above maps to the deterministic report — this is what gets auto-checked.
          </p>
          {data.traced_figures.map((fig, i) => (
            <div className="traced-item" key={i}>
              <span className="traced-value">{fig.display_value}</span>
              <span className="traced-source">{fig.source_label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
