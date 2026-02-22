import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

const navLinks = [
  { path: '/', label: 'Home' },
  { path: '/about', label: 'About' },
  { path: '/contact', label: 'Contact' },
  { path: '/live', label: 'ThermalScout' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen flex flex-col bg-uber-black">
      <header className="bg-uber-white border-b border-uber-gray-light text-uber-gray-dark px-4 sm:px-6 py-4">
        <nav className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 max-w-6xl mx-auto">
          <Link to="/" className="flex items-center gap-2 sm:gap-3 text-lg font-medium tracking-tight">
            <img src="/thermoscout_logo.png" alt="ThermalScout" className="h-8 w-auto" />
            <span className="text-cyan-400">ThermalScout</span>
            <span className="text-sm text-uber-gray-mid font-normal hidden sm:inline border-l border-uber-gray-light pl-3">Autonomous Radiator Thermal Mapping</span>
          </Link>
          <div className="flex gap-6 sm:gap-8">
            {navLinks.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`text-sm font-medium transition-colors ${
                  location.pathname === path
                    ? 'text-uber-gray-dark'
                    : 'text-uber-gray-mid hover:text-uber-gray-dark'
                }`}
              >
                {label}
              </Link>
            ))}
          </div>
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
