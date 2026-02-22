export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-light tracking-tight text-uber-gray-dark">
            About the Project
          </h2>
          <p className="mt-4 text-uber-gray-mid leading-relaxed">
            The dashboard provides a clean interface to visualise robot telemetry 
            and environmental data in real-time.
          </p>
        </section>
        <section>
          <h3 className="text-lg font-medium text-uber-gray-dark">Features</h3>
          <ul className="mt-3 space-y-2 text-uber-gray-mid">
            <li>Real-time 3D robot visualisation.</li>
            <li>Point cloud environment mapping.</li>
            <li>Minimalist dashboard for sensor data.</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
