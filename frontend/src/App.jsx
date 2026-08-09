import { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
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
 *
 * If data has already been uploaded (dates exist in the DB),
 * the app auto-redirects to Reconciliation instead of forcing
 * the user back through the Upload flow.
 */
export default function App() {
  const [clinicId, setClinicId] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)
  const [availableDates, setAvailableDates] = useState([])
  const [initialLoad, setInitialLoad] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  // Load available dates on mount — if data exists, auto-select
  // the most recent date and redirect away from Upload.
  useEffect(() => {
    getAvailableDates()
      .then((dates) => {
        setAvailableDates(dates)
        if (dates.length > 0) {
          setClinicId(dates[0].clinic_id)
          setSelectedDate(dates[0].date)

          // If we're on the Upload page and data already exists,
          // redirect to Reconciliation so users don't have to re-upload.
          if (location.pathname === '/') {
            navigate('/reconciliation', { replace: true })
          }
        }
      })
      .finally(() => setInitialLoad(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Don't render until we know if data exists (prevents flash)
  if (initialLoad) {
    return (
      <div className="app-layout">
        <Sidebar hasData={false} />
        <main className="main-content">
          <div className="loading-state">
            <div className="loading-spinner" />
            Loading...
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="app-layout">
      <Sidebar hasData={availableDates.length > 0} />
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
