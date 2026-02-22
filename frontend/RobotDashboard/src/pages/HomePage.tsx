import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
      <div className="space-y-10">
        <div className="card-gradient card-shine rounded-2xl p-8 sm:p-10 transition-all duration-300 hover:border-[var(--accent-cyan)]/20 animate-fade-slide">
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-uber-gray-dark">
            Heat Mapping Robot
          </h1>
          <p className="mt-5 text-lg text-uber-gray-mid max-w-2xl leading-relaxed">
            Monitor and visualise your robot's environment in real time.
          </p>
        </div>

        <div
          className="animate-fade-slide opacity-0"
          style={{ animationDelay: '0.15s' }}
        >
          <Link
            to="/live"
            className="card-gradient card-shine group inline-flex items-center gap-2 rounded-xl px-8 py-3.5 text-sm font-medium text-[var(--accent-cyan)] border border-[var(--accent-cyan)]/30 transition-all duration-300 hover:border-[var(--accent-cyan)]/60 hover:shadow-[0_0_24px_rgba(0,212,170,0.15)]"
          >
            <span>Open ThermalScout</span>
            <span className="transition-transform duration-300 group-hover:translate-x-1">→</span>
          </Link>
        </div>
      </div>
    </div>
  )
}
