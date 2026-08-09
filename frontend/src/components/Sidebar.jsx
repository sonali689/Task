import { NavLink } from 'react-router-dom'

/**
 * Persistent sidebar with navigation.
 * Shows dots with labels that expand on hover.
 * Upload link only appears as a small "+" button to avoid
 * confusing users who already have data loaded.
 */
const navItems = [
  { to: '/reconciliation', label: 'Reconciliation' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/narrative', label: 'AI Summary' },
]

export default function Sidebar({ hasData }) {
  return (
    <nav className="sidebar" id="sidebar-nav">
      {/* Logo area */}
      <div className="sidebar-logo">SQ</div>

      {/* Upload button (always available) */}
      <NavLink
        to="/"
        end
        className={({ isActive }) =>
          `sidebar-item ${isActive ? 'active' : ''}`
        }
        id="nav-upload"
      >
        <span className="sidebar-dot" />
        <span className="sidebar-label">Upload</span>
      </NavLink>

      {/* Divider */}
      <div className="sidebar-divider" />

      {/* Main navigation items */}
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `sidebar-item ${isActive ? 'active' : ''} ${!hasData ? 'disabled' : ''}`
          }
          id={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
          onClick={(e) => {
            if (!hasData) e.preventDefault()
          }}
        >
          <span className="sidebar-dot" />
          <span className="sidebar-label">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
