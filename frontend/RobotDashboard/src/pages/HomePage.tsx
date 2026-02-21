import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
      <div className="space-y-12">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-uber-black">
            Heat Mapping Robot
          </h1>
          <p className="mt-4 text-lg text-uber-gray-mid max-w-2xl">
            Monitor and visualise your robot's environment in real time.
          </p>
        </div>
        <div className="pt-8">
          <Link
            to="/dashboard"
            className="inline-block bg-uber-black text-uber-white px-8 py-3 text-sm font-medium rounded-sm hover:bg-uber-gray-dark transition-colors"
          >
            Open Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}
