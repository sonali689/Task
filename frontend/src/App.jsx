import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Upload from './pages/Upload'
import Reconciliation from './pages/Reconciliation'
import Analytics from './pages/Analytics'
import Narrative from './pages/Narrative'
import { getAvailableDates } from './api/client'

/**
 * Main application shell.
 * Manages shared state (selected clinic + date) and renders
 * the persistent sidebar + routed page content.
 */
export default function App() {
  const [clinicId, setClinicId] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)
  const [availableDates, setAvailableDates] = useState([])

  // Load available dates on mount
  useEffect(() => {
    getAvailableDates().then((dates) => {
      setAvailableDates(dates)
      if (dates.length > 0) {
        setClinicId(dates[0].clinic_id)
        setSelectedDate(dates[0].date)
      }
    })
  }, [])

  const handleUploadSuccess = (newClinicId, newDate) => {
    setClinicId(newClinicId)
    setSelectedDate(newDate)
    // Refresh available dates
    getAvailableDates().then(setAvailableDates)
  }

  const handleDateChange = (date) => {
    const entry = availableDates.find((d) => d.date === date)
    if (entry) {
      setClinicId(entry.clinic_id)
      setSelectedDate(date)
    }
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        {/* Date selector (shown when there are uploaded dates) */}
        {availableDates.length > 0 && (
          <div className="date-selector" id="date-selector">
            {availableDates.map((d) => (
              <button
                key={d.date}
                className={`date-btn ${d.date === selectedDate ? 'active' : ''}`}
                onClick={() => handleDateChange(d.date)}
              >
                {new Date(d.date + 'T00:00:00').toLocaleDateString('en-IN', {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
                {' '}({d.record_count} records)
              </button>
            ))}
          </div>
        )}

        <Routes>
          <Route
            path="/"
            element={<Upload onUploadSuccess={handleUploadSuccess} />}
          />
          <Route
            path="/reconciliation"
            element={<Reconciliation clinicId={clinicId} date={selectedDate} />}
          />
          <Route
            path="/analytics"
            element={<Analytics clinicId={clinicId} date={selectedDate} />}
          />
          <Route
            path="/narrative"
            element={<Narrative clinicId={clinicId} date={selectedDate} />}
          />
        </Routes>
      </main>
    </div>
  )
}
