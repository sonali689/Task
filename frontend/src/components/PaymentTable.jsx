import { formatRupees } from '../api/client'

/**
 * Payment mode breakdown table matching the assignment screenshot.
 * Shows Billed, Collected, Outstanding for each payment mode (Cash, Card, UPI).
 */
export default function PaymentTable({ breakdown }) {
  if (!breakdown || breakdown.length === 0) return null

  const modeLabels = { cash: 'Cash', card: 'Card', upi: 'UPI' }

  return (
    <div className="card-panel" id="payment-breakdown">
      <h2>Payment Mode Breakdown</h2>
      <table className="payment-table">
        <thead>
          <tr>
            <th>Mode</th>
            <th>Billed</th>
            <th>Collected</th>
            <th>Outstanding</th>
          </tr>
        </thead>
        <tbody>
          {breakdown.map((item) => (
            <tr key={item.mode}>
              <td>{modeLabels[item.mode] || item.mode}</td>
              <td>{formatRupees(item.billed_paise)}</td>
              <td>{formatRupees(item.collected_paise)}</td>
              <td>{formatRupees(item.outstanding_paise)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
