import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'

const LiveDashboardPage = lazy(() => import('./pages/LiveDashboardPage'))

export default function App() {
  return (
    <Layout>
      <Suspense fallback={
        <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] gap-4">
          <div className="w-10 h-10 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
          <p className="text-sm text-uber-gray-mid">Loading ThermalScout…</p>
        </div>
      }>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/dashboard" element={<Navigate to="/live" replace />} />
          <Route path="/live" element={<LiveDashboardPage />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}
