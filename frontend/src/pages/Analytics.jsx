import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { getAnalytics, formatRupees } from '../api/client'

/**
 * Screen 2: Analytics Dashboard
 * Matches the assignment screenshot exactly:
 * - Revenue by Hour of Day bar chart with peak hour highlighted
 * - Top Medicines by Quantity (ranked list)
 * - Top Medicines by Revenue (ranked list)
 */
export default function Analytics({ clinicId, date }) {
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
    getAnalytics(clinicId, date)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [clinicId, date])

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        Loading analytics...
      </div>
    )
  }

  if (error) {
    return <div className="error-banner">⚠️ {error}</div>
  }

  if (!report) {
    return (
      <div className="empty-state">
        <div className="emoji">📈</div>
        <h2>No Data Available</h2>
        <p>Upload a billing log to see analytics.</p>
      </div>
    )
  }

  // Check if there's any data to show
  const hasData = report.revenue_by_hour.length > 0

  if (!hasData) {
    return (
      <div id="analytics-page">
        <div className="page-header">
          <h1>Analytics</h1>
          <p className="subtitle">Mehta Multi-Specialty Clinic — {formatDisplayDate(date)}</p>
        </div>
        <div className="empty-state">
          <div className="emoji">📈</div>
          <h2>No Activity This Day</h2>
          <p>No non-refund transactions were recorded.</p>
        </div>
      </div>
    )
  }

  // Prepare chart data
  const chartData = report.revenue_by_hour.map((h) => ({
    name: h.hour_label,
    revenue: h.revenue_paise,
    isPeak: report.peak_hour && h.hour === report.peak_hour.hour,
  }))

  // Peak hour info
  const peakLabel = report.peak_hour
    ? (() => {
        const h = report.peak_hour.hour
        const nextH = h + 1
        const nextLabel =
          nextH === 0 || nextH === 24 ? '12am'
          : nextH < 12 ? `${nextH}am`
          : nextH === 12 ? '12pm'
          : `${nextH - 12}pm`
        return `Peak: ${report.peak_hour.hour_label}–${nextLabel} — ${formatRupees(report.peak_hour.revenue_paise)}`
      })()
    : null

  return (
    <div id="analytics-page">
      <div className="page-header">
        <h1>Analytics</h1>
        <p className="subtitle">Mehta Multi-Specialty Clinic — {formatDisplayDate(date)}</p>
      </div>

      {/* Revenue by Hour Chart */}
      <div className="chart-panel" id="revenue-chart">
        <h2>Revenue by Hour of Day</h2>
        {peakLabel && <div className="peak-badge">{peakLabel}</div>}
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 13, fill: '#6b7280' }}
            />
            <YAxis hide />
            <Tooltip
              formatter={(val) => [formatRupees(val), 'Revenue']}
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #e8ecf1',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            />
            <Bar dataKey="revenue" radius={[6, 6, 0, 0]} maxBarSize={56}>
              {chartData.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.isPeak ? '#3b82f6' : '#c7d2fe'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Drug Rankings */}
      <div className="rankings-grid">
        <div className="ranking-card" id="ranking-by-qty">
          <h2>Top Medicines — by Quantity</h2>
          {report.top_drugs_by_qty.map((drug) => (
            <div className="ranking-item" key={drug.drug_name}>
              <span className="rank">{drug.rank}</span>
              <span className="drug-name">{drug.drug_name}</span>
              <span className="drug-value">{drug.display_value}</span>
            </div>
          ))}
        </div>

        <div className="ranking-card" id="ranking-by-revenue">
          <h2>Top Medicines — by Revenue</h2>
          {report.top_drugs_by_revenue.map((drug) => (
            <div className="ranking-item" key={drug.drug_name}>
              <span className="rank">{drug.rank}</span>
              <span className="drug-name">{drug.drug_name}</span>
              <span className="drug-value">{drug.display_value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatDisplayDate(date) {
  return new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
