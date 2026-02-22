interface SensorState {
  ultrasonic_distance_cm?: number
  temperature_c?: number
  humidity_percent?: number
  room_id?: string
}

interface SensorReadoutProps {
  state: SensorState | null | undefined
}

export default function SensorReadout({ state }: SensorReadoutProps) {
  if (!state) {
    return (
      <div className="bg-uber-white/90 border border-uber-gray-light rounded-lg p-4 transition-all duration-200 hover:scale-[1.02] hover:shadow-lg">
        <h3 className="m-0 mb-3 text-base font-semibold text-uber-gray-dark">Live Sensors</h3>
        <p className="text-sm text-uber-gray-mid">Waiting for data…</p>
      </div>
    )
  }
  return (
    <div className="bg-uber-white/90 border border-uber-gray-light rounded-lg p-4 transition-all duration-200 hover:scale-[1.02] hover:shadow-lg">
      <h3 className="m-0 mb-3 text-base font-semibold text-uber-gray-dark">Live Sensors</h3>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-uber-gray-mid">Ultrasonic</span>
          <span className="font-mono text-sm font-medium text-uber-gray-dark">
            {state.ultrasonic_distance_cm?.toFixed(0) ?? '—'} cm
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-uber-gray-mid">Temperature</span>
          <span className="font-mono text-sm font-medium text-uber-gray-dark">
            {state.temperature_c?.toFixed(1) ?? '—'} °C
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-uber-gray-mid">Humidity</span>
          <span className="font-mono text-sm font-medium text-uber-gray-dark">
            {state.humidity_percent?.toFixed(0) ?? '—'} %
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-uber-gray-mid">Location</span>
          <span className="font-mono text-sm font-medium text-uber-gray-dark">
            {state.room_id ?? 'corridor'}
          </span>
        </div>
      </div>
    </div>
  )
}
