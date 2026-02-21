import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

const navLinks = [
  { path: '/', label: 'Home' },
  { path: '/about', label: 'About' },
  { path: '/contact', label: 'Contact' },
  { path: '/dashboard', label: 'Dashboard' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen flex flex-col bg-uber-white">
      <header className="bg-uber-black text-uber-white px-4 sm:px-6 py-4">
        <nav className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 max-w-6xl mx-auto">
          <Link to="/" className="text-lg font-medium tracking-tight">
            Robot Dashboard
          </Link>
          <div className="flex gap-6 sm:gap-8">
            {navLinks.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`text-sm font-medium transition-colors ${
                  location.pathname === path
                    ? 'text-uber-white'
                    : 'text-uber-gray-light hover:text-uber-white'
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
