import { NavLink } from 'react-router-dom'

/**
 * Persistent sidebar with navigation dots matching the assignment screenshots.
 * Shows dots for each screen with active state indication.
 */
const navItems = [
  { to: '/', label: 'Upload' },
  { to: '/reconciliation', label: 'EOD Reconciliation' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/narrative', label: 'AI Narrative' },
]

export default function Sidebar() {
  return (
    <nav className="sidebar" id="sidebar-nav">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `sidebar-dot ${isActive ? 'active' : ''}`
          }
          id={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
        >
          <span className="tooltip">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
