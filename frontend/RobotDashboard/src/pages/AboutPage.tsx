export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <div className="space-y-8">
        <section className="card-gradient card-shine rounded-2xl p-8 sm:p-10 transition-all duration-300 hover:border-[var(--accent-cyan)]/20 animate-fade-slide">
          <h2 className="text-2xl font-light tracking-tight text-uber-gray-dark">
            About the Project
          </h2>
          <p className="mt-5 text-uber-gray-mid leading-relaxed">
            The dashboard provides a clean interface to visualise robot telemetry
            and environmental data in real-time.
          </p>
        </section>

        <section
          className="card-gradient card-shine rounded-2xl p-8 sm:p-10 transition-all duration-300 hover:border-[var(--accent-cyan)]/20 animate-fade-slide opacity-0"
          style={{ animationDelay: '0.15s' }}
        >
          <h3 className="text-lg font-medium text-uber-gray-dark">Features</h3>
          <ul className="mt-5 space-y-3">
            {[
              'Real-time 3D robot visualisation.',
              'Point cloud environment mapping.',
              'Minimalist dashboard for sensor data.',
            ].map((item, i) => (
              <li
                key={i}
                className="flex items-center gap-3 text-uber-gray-mid transition-colors duration-200 hover:text-[var(--accent-cyan)]"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-cyan)]/60" />
                {item}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
