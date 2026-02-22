import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
      <div className="space-y-12">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-uber-gray-dark">
            Heat Mapping Robot
          </h1>
          <p className="mt-4 text-lg text-uber-gray-mid max-w-2xl">
            Monitor and visualise your robot's environment in real time.
          </p>
        </div>
        <div className="pt-8">
          <Link
            to="/live"
            className="inline-block bg-[var(--accent-cyan)] text-uber-black px-8 py-3 text-sm font-medium rounded-sm hover:opacity-90 transition-opacity"
          >
            Open ThermalScout
          </Link>
        </div>
      </div>
    </div>
  )
}
