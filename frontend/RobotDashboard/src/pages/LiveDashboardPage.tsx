import { useState, useEffect } from 'react'
import LiveMap from '../components/LiveMap'
import RobotScene3D from '../components/RobotScene3D'
import AnalyticsPanel from '../components/AnalyticsPanel'
import Alerts from '../components/Alerts'
import SensorReadout from '../components/SensorReadout'
import DashboardSkeleton from '../components/DashboardSkeleton'

const WS_URL =
  (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host

interface RobotState {
  position?: { x: number; y: number; theta?: number }
  ultrasonic_distance_cm?: number
  temperature_c?: number
  humidity_percent?: number
  room_id?: string
}

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

export default function LiveDashboardPage() {
  const [state, setState] = useState<RobotState | null>(null)
  const [rooms, setRooms] = useState<RoomAnalytics[]>([])
  const [trail, setTrail] = useState<[number, number][]>([])
  const [grid, setGrid] = useState<number[][]>([])
  const [rows, setRows] = useState(0)
  const [cols, setCols] = useState(0)
  const [heatmapCells, setHeatmapCells] = useState<Record<string, number>>({})
  const [heatmapRows, setHeatmapRows] = useState(0)
  const [heatmapCols, setHeatmapCols] = useState(0)
  const [obstaclePoints, setObstaclePoints] = useState<number[][]>([])
  const [pointCloud, setPointCloud] = useState<number[][]>([])
  const [connected, setConnected] = useState(false)
  const [hasData, setHasData] = useState(false)
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('3d')
  const [liveOpacity, setLiveOpacity] = useState(1)

  useEffect(() => {
    const ready = connected || grid.length > 0 || (state?.position != null) || rooms.length > 0
    setHasData(ready)
  }, [connected, grid.length, state?.position, rooms.length])

  useEffect(() => {
    if (!connected) return
    let rafId: number
    const start = performance.now()
    const tick = () => {
      const t = (performance.now() - start) / 1000
      const opacity = 0.4 + 0.6 * (1 + Math.sin(t * 2.5)) / 2
      setLiveOpacity(opacity)
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [connected])

  useEffect(() => {
    const ws = new WebSocket(WS_URL + '/ws/live')
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'analytics') {
          setRooms(data.rooms || [])
          setTrail(data.trail || [])
          if (data.heatmap_cells) setHeatmapCells(data.heatmap_cells)
          if (data.heatmap_rows != null) setHeatmapRows(data.heatmap_rows)
          if (data.heatmap_cols != null) setHeatmapCols(data.heatmap_cols)
          if (Array.isArray(data.obstacle_points)) setObstaclePoints(data.obstacle_points)
          if (Array.isArray(data.point_cloud)) setPointCloud(data.point_cloud)
        } else if (data.position) {
          setState(data)
        } else {
          setState(data)
        }
      } catch {
        // ignore parse errors
      }
    }
    return () => ws.close()
  }, [])

  useEffect(() => {
    const fetchMap = () =>
      fetch('/api/map')
        .then((r) => r.json())
        .then((d: { grid?: number[][]; rows?: number; cols?: number; trail?: [number, number][]; heatmap_cells?: Record<string, number>; heatmap_rows?: number; heatmap_cols?: number; obstacle_points?: number[][]; point_cloud?: number[][] }) => {
          setGrid(d.grid || [])
          setRows(d.rows || 0)
          setCols(d.cols || 0)
          if (!connected) setTrail(d.trail || [])
          if (d.heatmap_cells) setHeatmapCells(d.heatmap_cells)
          if (d.heatmap_rows != null) setHeatmapRows(d.heatmap_rows)
          if (d.heatmap_cols != null) setHeatmapCols(d.heatmap_cols)
          if (Array.isArray(d.obstacle_points)) setObstaclePoints(d.obstacle_points)
          if (Array.isArray(d.point_cloud)) setPointCloud(d.point_cloud)
        })
        .catch(() => {})

    const fetchCurrent = () =>
      fetch('/api/current')
        .then((r) => r.json())
        .then((d: { position?: { x: number; y: number; theta?: number }; ultrasonic_distance_cm?: number }) => {
          if (d.position != null || d.ultrasonic_distance_cm != null) setState(d)
        })
        .catch(() => {})

    const fetchRooms = () =>
      fetch('/api/rooms')
        .then((r) => r.json())
        .then((d: { rooms?: RoomAnalytics[] }) => {
          if (d.rooms?.length) setRooms(d.rooms)
        })
        .catch(() => {})

    // Fire all three in parallel for faster initial load
    fetchMap()
    fetchCurrent()
    fetchRooms()

    const interval = connected ? 2000 : 500
    const id = setInterval(() => {
      fetchMap()
      if (!connected) {
        fetchCurrent()
        fetchRooms()
      }
    }, interval)
    return () => clearInterval(id)
  }, [connected])

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      <header className="px-4 sm:px-6 py-4 bg-[#1a2332] border-b border-[#30363d] flex flex-wrap items-center gap-4">
        <h1 className="m-0 text-xl font-bold text-cyan-400">ThermalScout</h1>
        <span className="text-sm text-uber-gray-mid">Autonomous Radiator Thermal Mapping</span>
        <div className={`ml-auto font-mono text-sm flex items-center gap-1.5 ${hasData ? 'text-cyan-400' : 'text-uber-gray-mid'}`}>
          {hasData ? (
            <>
              <span className="inline-block" style={{ opacity: connected ? liveOpacity : 1 }}>●</span>
              <span>{connected ? 'LIVE' : 'Live (polling)'}</span>
            </>
          ) : (
            '○ Connecting...'
          )}
        </div>
      </header>

      {hasData ? (
        <main className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 p-4 overflow-visible animate-fade-slide">
          <section className="relative z-0 bg-[#1a2332] rounded-lg border border-[#30363d] overflow-hidden min-h-[400px] flex flex-col">
            <div className="flex gap-0 p-1 pt-1 pr-1 pl-1 pb-0 bg-[#243044] border-b border-[#30363d]">
              <button
                type="button"
                className={`flex-1 py-2 px-3 text-sm font-medium border-none rounded-t-lg transition-all duration-150 cursor-pointer ${
                  viewMode === '2d'
                    ? 'bg-[#1a2332] text-cyan-400'
                    : 'bg-transparent text-uber-gray-mid hover:text-uber-gray-dark'
                }`}
                onClick={() => setViewMode('2d')}
              >
                2D Map
              </button>
              <button
                type="button"
                className={`flex-1 py-2 px-3 text-sm font-medium border-none rounded-t-lg transition-all duration-150 cursor-pointer ${
                  viewMode === '3d'
                    ? 'bg-[#1a2332] text-cyan-400'
                    : 'bg-transparent text-uber-gray-mid hover:text-uber-gray-dark'
                }`}
                onClick={() => setViewMode('3d')}
              >
                3D Robot
              </button>
            </div>
            <div className="flex-1 min-h-[450px] flex flex-col">
              {viewMode === '2d' ? (
                <div className="flex-1">
                  <LiveMap
                    grid={grid}
                    rows={rows}
                    cols={cols}
                    heatmapRows={heatmapRows}
                    heatmapCols={heatmapCols}
                    state={state}
                    trail={trail}
                    heatmapCells={heatmapCells}
                  />
                </div>
              ) : (
                <div className="flex-1 min-h-[450px]">
                  <RobotScene3D
                    state={state}
                    trail={trail}
                    grid={grid}
                    rows={rows}
                    cols={cols}
                    heatmapRows={heatmapRows}
                    heatmapCols={heatmapCols}
                    heatmapCells={heatmapCells}
                    obstaclePoints={obstaclePoints}
                    pointCloud={pointCloud}
                    connected={connected}
                  />
                </div>
              )}
            </div>
          </section>

          <aside className="relative z-10 flex flex-col gap-4 overflow-y-auto overflow-x-hidden min-w-0 shrink-0 px-2 py-1">
            <SensorReadout state={state} />
            <AnalyticsPanel rooms={rooms} />
            <Alerts rooms={rooms} />
          </aside>
        </main>
      ) : (
        <DashboardSkeleton />
      )}
    </div>
  )
}
