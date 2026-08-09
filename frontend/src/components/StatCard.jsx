/**
 * Reusable stat card component for the reconciliation dashboard.
 * Displays a labeled metric with a value and optional sub-label.
 */
export default function StatCard({ label, value, subLabel, variant }) {
  return (
    <div className={`stat-card ${variant}`} id={`stat-${variant}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {subLabel && <div className="sub-label">{subLabel}</div>}
    </div>
  )
}
