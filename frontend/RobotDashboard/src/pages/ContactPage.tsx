export default function ContactPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-light tracking-tight text-uber-gray-dark">
            Contact Us
          </h2>
          <p className="mt-4 text-uber-gray-mid leading-relaxed">
            For inquiries about the Heat Mapping Robot project or collaboration opportunities, 
            please reach out to the team through HackLondon 2026 channels.
          </p>
        </section>
        <section className="pt-4">
          <h3 className="text-lg font-medium text-uber-gray-dark">Team</h3>
          <ul className="mt-3 space-y-1 text-uber-gray-mid">
            <li>Thomas Moody</li>
            <li>Naerthi Senthilkumar</li>
            <li>Helitha Cooray</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
