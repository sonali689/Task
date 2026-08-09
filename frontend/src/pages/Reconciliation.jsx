import { useState, useEffect } from 'react'
import { getReconciliation, formatRupees } from '../api/client'
import StatCard from '../components/StatCard'
import PaymentTable from '../components/PaymentTable'

/**
 * Screen 1: EOD Reconciliation Dashboard
 * Matches the assignment screenshot:
 * - 4 stat cards: Total Billed, Total Collected, Outstanding, Refunds
 * - Discounts shown as a supplementary badge
 * - Payment Mode Breakdown table
 */
export default function Reconciliation({ clinicId, date }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!clinicId || !date) {
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    getReconciliation(clinicId, date)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [clinicId, date])

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        Loading reconciliation...
      </div>
    )
  }

  if (error) {
    return <div className="error-banner">⚠️ {error}</div>
  }

  if (!report) {
    return (
      <div className="empty-state">
        <div className="emoji">📊</div>
        <h2>No Data Available</h2>
        <p>Upload a billing log to see the reconciliation report.</p>
      </div>
    )
  }

  // Collection percentage
  const collectionPct = report.total_billed_paise > 0
    ? Math.round((report.total_collected_paise / report.total_billed_paise) * 100)
    : 0

  // Format date for display
  const displayDate = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  return (
    <div id="reconciliation-page">
      <div className="page-header">
        <h1>EOD Reconciliation</h1>
        <p className="subtitle">Mehta Multi-Specialty Clinic — Kanpur, Uttar Pradesh</p>
        <div className="date-badge">
          {displayDate}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </div>
      </div>

      <div className="stat-cards">
        <StatCard
          label="TOTAL BILLED"
          value={formatRupees(report.total_billed_paise)}
          subLabel={`${report.total_visits} visits`}
          variant="billed"
        />
        <StatCard
          label="TOTAL COLLECTED"
          value={formatRupees(report.total_collected_paise)}
          subLabel={`${collectionPct}% of billed`}
          variant="collected"
        />
        <StatCard
          label="OUTSTANDING"
          value={formatRupees(report.outstanding_paise)}
          subLabel={`${report.pending_visits} pending visits`}
          variant="outstanding"
        />
        <StatCard
          label="REFUNDS"
          value={formatRupees(report.total_refunds_paise)}
          subLabel={`${report.refund_count} refund${report.refund_count !== 1 ? 's' : ''}`}
          variant="refunds"
        />
      </div>

      {/* Show discounts if any were applied */}
      {report.total_discounts_paise > 0 && (
        <div className="discount-note" id="discount-note">
          💰 <strong>{formatRupees(report.total_discounts_paise)}</strong> in discounts applied today
          <span className="discount-detail">
            — billed amount shown is net of discounts (after subtracting discount from line-item totals)
          </span>
        </div>
      )}

      <PaymentTable breakdown={report.payment_mode_breakdown} />

      {report.validation_errors?.length > 0 && (
        <div className="validation-warnings">
          <h3>⚠️ {report.validation_errors.length} row(s) were rejected during import:</h3>
          <ul>
            {report.validation_errors.map((err, i) => (
              <li key={i}>{err.message}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
