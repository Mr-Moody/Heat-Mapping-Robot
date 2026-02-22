interface RoomAnalytics {
  room_id: number
  room_name: string
  avg_temperature_c: number
  delta_t_from_setpoint: number
  wasted_power_w: number
  humidity_percent: number
  sustainability_score: number
  energy_waste_risk?: boolean
}

interface AnalyticsPanelProps {
  rooms: RoomAnalytics[] | null | undefined
}

export default function AnalyticsPanel({ rooms }: AnalyticsPanelProps) {
  return (
    <div className="bg-uber-white/90 border border-uber-gray-light rounded-lg p-4 transition-transform duration-200 hover:scale-[1.01] hover:shadow-md origin-center">
      <h2 className="m-0 mb-4 text-base font-semibold text-uber-gray-dark">Space analytics</h2>
      <div className="flex flex-col gap-3">
        {(rooms ?? []).map((r) => (
          <div
            key={r.room_id}
            className={`rounded-md border-l-4 bg-uber-white/60 p-3 transition-transform duration-200 hover:scale-[1.01] hover:shadow-md origin-center ${
              r.energy_waste_risk ? 'border-l-amber-500' : 'border-l-uber-gray-light'
            }`}
          >
            <div className="mb-2 text-sm font-semibold text-uber-gray-dark">{r.room_name}</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex flex-col gap-0.5">
                <span className="text-uber-gray-mid">Avg Temp</span>
                <span className="font-mono font-medium">{r.avg_temperature_c}°C</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-uber-gray-mid">ΔT (setpoint 19°C)</span>
                <span className={`font-mono font-medium ${r.delta_t_from_setpoint > 0 ? 'text-amber-600' : ''}`}>
                  {r.delta_t_from_setpoint > 0 ? '+' : ''}{r.delta_t_from_setpoint}°C
                </span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-uber-gray-mid">Est. Waste</span>
                <span className="font-mono font-medium text-red-600">{r.wasted_power_w} W</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-uber-gray-mid">Humidity</span>
                <span className="font-mono font-medium">{r.humidity_percent}%</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-uber-gray-mid">Score</span>
                <span className="font-mono font-medium">{r.sustainability_score}/100</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
