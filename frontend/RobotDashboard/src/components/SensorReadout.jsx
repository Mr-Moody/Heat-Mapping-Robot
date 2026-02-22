import './SensorReadout.css'

export default function SensorReadout({ state }) {
  if (!state) {
    return (
      <div className="sensor-readout">
        <h3>Live Sensors</h3>
        <p className="muted">Waiting for data…</p>
      </div>
    )
  }
  return (
    <div className="sensor-readout">
      <h3>Live Sensors</h3>
      <div className="sensors">
        <div className="sensor">
          <span className="label">Ultrasonic</span>
          <span className="value">{state.ultrasonic_distance_cm?.toFixed(0) ?? '—'} cm</span>
        </div>
        <div className="sensor">
          <span className="label">Temperature</span>
          <span className="value">{state.temperature_c?.toFixed(1) ?? '—'} °C</span>
        </div>
        <div className="sensor">
          <span className="label">Humidity</span>
          <span className="value">{state.humidity_percent?.toFixed(0) ?? '—'} %</span>
        </div>
        <div className="sensor">
          <span className="label">Location</span>
          <span className="value">{state.room_id ?? 'corridor'}</span>
        </div>
      </div>
    </div>
  )
}
