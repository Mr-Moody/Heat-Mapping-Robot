import './Alerts.css'

export default function Alerts({ rooms }) {
  const alerts = (rooms || [])
    .filter((r) => r.energy_waste_risk || r.overheating || r.ventilation_quality_flag)
    .map((r) => ({
      room: r.room_name,
      type: r.energy_waste_risk ? 'Energy Waste Risk' : r.ventilation_quality_flag ? 'Ventilation' : 'Overheating',
      detail:
        r.delta_t_from_setpoint > 2
          ? `ΔT > 2°C — ~${r.wasted_power_w}W continuous waste`
          : r.ventilation_quality_flag
          ? 'High temp variance — check ventilation'
          : 'Overheating detected',
    }))

  if (alerts.length === 0) return null

  return (
    <div className="alerts">
      <h2>Alerts</h2>
      <ul>
        {alerts.map((a, i) => (
          <li key={i} className="alert-item">
            <strong>{a.room}</strong>: {a.type} — {a.detail}
          </li>
        ))}
      </ul>
    </div>
  )
}
