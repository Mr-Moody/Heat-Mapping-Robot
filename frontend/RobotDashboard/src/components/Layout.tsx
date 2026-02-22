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
          <Link to="/" className="text-lg font-medium tracking-tight text-uber-gray-dark">
            Robot Dashboard
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
