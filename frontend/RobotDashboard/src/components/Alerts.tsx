interface RoomAlert {
  room_id: number
  room_name: string
  energy_waste_risk?: boolean
  overheating?: boolean
  ventilation_quality_flag?: boolean
  delta_t_from_setpoint?: number
  wasted_power_w?: number
}

interface AlertsProps {
  rooms: RoomAlert[] | null | undefined
}

export default function Alerts({ rooms }: AlertsProps) {
  const alerts = (rooms ?? [])
    .filter((r) => r.energy_waste_risk || r.overheating || r.ventilation_quality_flag)
    .map((r) => ({
      room: r.room_name,
      type: r.energy_waste_risk ? 'Energy Waste Risk' : r.ventilation_quality_flag ? 'Ventilation' : 'Overheating',
      detail:
        (r.delta_t_from_setpoint ?? 0) > 2
          ? `ΔT > 2°C — ~${r.wasted_power_w ?? 0}W continuous waste`
          : r.ventilation_quality_flag
            ? 'High temp variance — check ventilation'
            : 'Overheating detected',
    }))

  if (alerts.length === 0) return null

  return (
    <div className="bg-uber-white/90 border border-uber-gray-light rounded-lg p-4 transition-transform duration-200 hover:scale-[1.01] hover:shadow-md origin-center">
      <h2 className="m-0 mb-3 text-base font-semibold text-uber-gray-dark">Alerts</h2>
      <ul className="m-0 list-disc pl-5">
        {alerts.map((a, i) => (
          <li key={i} className="mb-2 text-sm text-amber-600">
            <strong className="text-uber-gray-dark">{a.room}</strong>: {a.type} — {a.detail}
          </li>
        ))}
      </ul>
    </div>
  )
}
