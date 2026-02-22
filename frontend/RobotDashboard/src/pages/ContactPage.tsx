const team = [
  { name: 'Thomas Moody', linkedIn: 'https://www.linkedin.com/in/thomas-moody1/' },
  { name: 'Naerthi Senthilkumar', linkedIn: 'https://www.linkedin.com/in/naerthi-senthilkumar-83851a298/' },
  { name: 'Helitha Cooray', linkedIn: 'https://www.linkedin.com/in/helitha-cooray/' },
]

export default function ContactPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
      <div className="space-y-8">
        <section className="card-gradient card-shine rounded-2xl p-8 sm:p-10 transition-all duration-300 hover:border-[var(--accent-cyan)]/20 animate-fade-slide">
          <h2 className="text-2xl font-light tracking-tight text-uber-gray-dark">
            Contact Us
          </h2>
          <p className="mt-5 text-uber-gray-mid leading-relaxed">
            For inquiries about the Heat Mapping Robot project or collaboration
            opportunities, please reach out to the team through HackLondon 2026
            channels.
          </p>
        </section>

        <section
          className="card-gradient card-shine rounded-2xl p-8 sm:p-10 transition-all duration-300 hover:border-[var(--accent-cyan)]/20 animate-fade-slide opacity-0"
          style={{ animationDelay: '0.15s' }}
        >
          <h3 className="text-lg font-medium text-uber-gray-dark">Team</h3>
          <ul className="mt-5 space-y-2">
            {team.map((member, i) => (
              <li key={i}>
                <a
                  href={member.linkedIn}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-lg px-4 py-3 text-uber-gray-mid transition-all duration-200 hover:bg-[var(--bg-elevated)]/50 hover:text-[var(--accent-cyan)]"
                >
                  {member.name}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
