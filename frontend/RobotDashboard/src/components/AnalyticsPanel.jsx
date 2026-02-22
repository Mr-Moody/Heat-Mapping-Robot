import './AnalyticsPanel.css'

export default function AnalyticsPanel({ rooms }) {
  return (
    <div className="analytics-panel">
      <h2>Space analytics</h2>
      <div className="room-list">
        {(rooms || []).map((r) => (
          <div
            key={r.room_id}
            className={`room-card ${r.energy_waste_risk ? 'risk' : ''}`}
          >
            <div className="room-name">{r.room_name}</div>
            <div className="metrics">
              <div className="metric">
                <span className="label">Avg Temp</span>
                <span className="value">{r.avg_temperature_c}°C</span>
              </div>
              <div className="metric">
                <span className="label">ΔT (setpoint 19°C)</span>
                <span className={`value ${r.delta_t_from_setpoint > 0 ? 'over' : ''}`}>
                  {r.delta_t_from_setpoint > 0 ? '+' : ''}{r.delta_t_from_setpoint}°C
                </span>
              </div>
              <div className="metric">
                <span className="label">Est. Waste</span>
                <span className="value waste">{r.wasted_power_w} W</span>
              </div>
              <div className="metric">
                <span className="label">Humidity</span>
                <span className="value">{r.humidity_percent}%</span>
              </div>
              <div className="metric">
                <span className="label">Score</span>
                <span className="value">{r.sustainability_score}/100</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
