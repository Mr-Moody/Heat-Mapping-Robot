/**
 * Skeleton placeholder matching LiveDashboard layout.
 * Shows UI outline while loading (Google/Twitter/Discord style).
 */
export default function DashboardSkeleton() {
  return (
    <main className="flex-1 grid grid-cols-1 lg:grid-cols-[200px_1fr_320px] gap-4 p-4 overflow-visible">
      {/* Robot list panel skeleton */}
      <aside className="hidden lg:flex flex-col gap-3 min-w-[200px] w-[200px] shrink-0 py-2">
        <div className="skeleton h-3 w-14 rounded px-2" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-lg border border-[#30363d] p-2 space-y-2">
            <div className="skeleton aspect-[4/3] w-full rounded" />
            <div className="skeleton h-4 w-20 rounded" />
          </div>
        ))}
      </aside>
      {/* Map section skeleton */}
      <section className="relative z-0 bg-[#1a2332] rounded-lg border border-[#30363d] overflow-hidden min-h-[400px] flex flex-col">
        {/* Tab bar */}
        <div className="flex gap-0 p-1 pt-1 pr-1 pl-1 pb-0 bg-[#243044] border-b border-[#30363d]">
          <div className="flex-1 py-2 px-3">
            <div className="skeleton h-4 w-16 rounded" />
          </div>
          <div className="flex-1 py-2 px-3">
            <div className="skeleton h-4 w-20 rounded" />
          </div>
        </div>
        {/* Map content area */}
        <div className="flex-1 min-h-[450px] p-4 flex flex-col gap-4">
          <div className="skeleton flex-1 min-h-[380px] rounded-lg" />
          <div className="flex gap-4">
            <div className="skeleton h-6 w-24 rounded" />
            <div className="skeleton h-6 w-32 rounded" />
          </div>
        </div>
      </section>

      {/* Sidebar skeleton */}
      <aside className="relative z-10 flex flex-col gap-4 overflow-hidden min-w-0 shrink-0 px-2 py-1">
        {/* Sensor card */}
        <div className="bg-[#1a2332]/90 border border-[#30363d] rounded-lg p-4">
          <div className="skeleton h-4 w-24 mb-3 rounded" />
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="skeleton h-3 w-16 rounded" />
                <div className="skeleton h-5 w-12 rounded" />
              </div>
            ))}
          </div>
        </div>
        {/* Analytics card */}
        <div className="bg-[#1a2332]/90 border border-[#30363d] rounded-lg p-4">
          <div className="skeleton h-4 w-32 mb-4 rounded" />
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-md border border-[#30363d] p-3 space-y-2">
                <div className="skeleton h-4 w-20 rounded" />
                <div className="grid grid-cols-2 gap-2">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j} className="flex flex-col gap-1">
                      <div className="skeleton h-3 w-12 rounded" />
                      <div className="skeleton h-4 w-10 rounded" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        {/* Alerts card */}
        <div className="bg-[#1a2332]/90 border border-[#30363d] rounded-lg p-4">
          <div className="skeleton h-4 w-16 mb-3 rounded" />
          <div className="space-y-2">
            <div className="skeleton h-4 w-full rounded" />
            <div className="skeleton h-4 w-[80%] rounded" />
          </div>
        </div>
      </aside>
    </main>
  )
}
