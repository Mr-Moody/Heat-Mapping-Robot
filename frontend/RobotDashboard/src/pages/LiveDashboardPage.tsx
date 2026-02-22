import { useState, useEffect } from 'react'
import LiveMap from '../components/LiveMap'
import RobotScene3D from '../components/RobotScene3D'
import AnalyticsPanel from '../components/AnalyticsPanel'
import Alerts from '../components/Alerts'
import SensorReadout from '../components/SensorReadout'
import DashboardSkeleton from '../components/DashboardSkeleton'
import RobotListPanel from '../components/RobotListPanel'
import MainContentSkeleton from '../components/MainContentSkeleton'
import type { RobotInfo } from '../components/RobotCard'

const WS_URL =
  (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host

interface RobotState {
  position?: { x: number; y: number; theta?: number }
  ultrasonic_distance_cm?: number
  temperature_c?: number
  humidity_percent?: number
  room_id?: string
  room_name?: string
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
  const [obstacleCells, setObstacleCells] = useState<[number, number][]>([])
  const [pointCloud, setPointCloud] = useState<number[][]>([])
  const [connected, setConnected] = useState(false)
  const [hasData, setHasData] = useState(false)
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('3d')
  const [liveOpacity, setLiveOpacity] = useState(1)

  const [robots, setRobots] = useState<RobotInfo[]>([])
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null)
  const [robotStates, setRobotStates] = useState<Record<string, RobotState | null>>({})
  const [isLoadingSelectedRobot, setIsLoadingSelectedRobot] = useState(false)

  useEffect(() => {
    const ready = connected || grid.length > 0 || (state?.position != null) || rooms.length > 0
    setHasData(ready)
  }, [connected, grid.length, state?.position, rooms.length])

  useEffect(() => {
    if (robots.length > 0 && !selectedRobotId) {
      const firstActive = robots.find((r) => r.active) ?? robots[0]
      setSelectedRobotId(firstActive.id)
      setIsLoadingSelectedRobot(true)
    }
  }, [robots, selectedRobotId])

  const handleSelectRobot = (id: string) => {
    if (id === selectedRobotId) return
    setSelectedRobotId(id)
    setIsLoadingSelectedRobot(true)
  }

  useEffect(() => {
    if (selectedRobotId && robotStates[selectedRobotId]) {
      setState(robotStates[selectedRobotId])
    }
  }, [selectedRobotId, robotStates])

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
    const fetchRobots = () =>
      fetch('/api/robots')
        .then((r) => r.json())
        .then((d: { robots?: RobotInfo[] }) => {
          if (Array.isArray(d.robots)) setRobots(d.robots)
        })
        .catch(() => {})
    fetchRobots()
    const id = setInterval(fetchRobots, 5000)
    return () => clearInterval(id)
  }, [])

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
        } else if (data.type === 'robot_update' && data.robot_id) {
          const rid = data.robot_id
          const s: RobotState = {
            position: data.position,
            ultrasonic_distance_cm: data.ultrasonic_distance_cm,
            temperature_c: data.temperature_c,
            humidity_percent: data.humidity_percent,
            room_id: data.room_id,
            room_name: data.room_name,
          }
          setRobotStates((prev) => ({ ...prev, [rid]: s }))
          if (rid === selectedRobotId) {
            setState(s)
            if (Array.isArray(data.trail)) setTrail(data.trail)
            if (data.heatmap_cells) setHeatmapCells(data.heatmap_cells)
            if (data.heatmap_rows != null) setHeatmapRows(data.heatmap_rows)
            if (data.heatmap_cols != null) setHeatmapCols(data.heatmap_cols)
            if (Array.isArray(data.obstacle_points)) setObstaclePoints(data.obstacle_points)
            if (Array.isArray(data.point_cloud)) setPointCloud(data.point_cloud)
            setIsLoadingSelectedRobot(false)
          }
        }
      } catch {
        // ignore parse errors
      }
    }
    return () => ws.close()
  }, [selectedRobotId])

  useEffect(() => {
    const rid = selectedRobotId
    const fetchMap = () =>
      fetch(rid ? `/api/map?robot_id=${encodeURIComponent(rid)}` : '/api/map')
        .then((r) => r.json())
        .then((d: { grid?: number[][]; rows?: number; cols?: number; trail?: [number, number][]; heatmap_cells?: Record<string, number>; heatmap_rows?: number; heatmap_cols?: number; obstacle_points?: number[][]; obstacle_cells?: [number, number][]; point_cloud?: number[][] }) => {
          setGrid(d.grid || [])
          setRows(d.rows || 0)
          setCols(d.cols || 0)
          if (Array.isArray(d.obstacle_cells)) setObstacleCells(d.obstacle_cells)
          if (!connected) {
            if (Array.isArray(d.trail)) setTrail(d.trail)
            if (d.heatmap_cells) setHeatmapCells(d.heatmap_cells)
            if (d.heatmap_rows != null) setHeatmapRows(d.heatmap_rows)
            if (d.heatmap_cols != null) setHeatmapCols(d.heatmap_cols)
            if (Array.isArray(d.obstacle_points)) setObstaclePoints(d.obstacle_points)
            if (Array.isArray(d.point_cloud)) setPointCloud(d.point_cloud)
          }
          setIsLoadingSelectedRobot(false)
        })
        .catch(() => {})

    const fetchCurrent = () =>
      fetch(rid ? `/api/current?robot_id=${encodeURIComponent(rid)}` : '/api/current')
        .then((r) => r.json())
        .then((d: RobotState & { robot_id?: string }) => {
          if (d.position != null || d.ultrasonic_distance_cm != null) {
            const s: RobotState = {
              position: d.position,
              ultrasonic_distance_cm: d.ultrasonic_distance_cm,
              temperature_c: d.temperature_c,
              humidity_percent: d.humidity_percent,
              room_id: d.room_id,
              room_name: d.room_name,
            }
            setState(s)
            if (d.robot_id) {
              setRobotStates((prev) => ({ ...prev, [d.robot_id!]: s }))
            }
            setIsLoadingSelectedRobot(false)
          }
        })
        .catch(() => {})

    const fetchRooms = () =>
      fetch('/api/rooms')
        .then((r) => r.json())
        .then((d: { rooms?: RoomAnalytics[] }) => {
          if (d.rooms?.length) setRooms(d.rooms)
        })
        .catch(() => {})

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
  }, [connected, selectedRobotId])

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      {hasData ? (
        <main className={`flex-1 grid grid-cols-1 gap-4 p-4 overflow-visible animate-fade-slide ${robots.length > 0 ? 'lg:grid-cols-[200px_1fr_320px]' : 'lg:grid-cols-[1fr_320px]'}`}>
          {robots.length > 0 && (
            <RobotListPanel
              robots={robots}
              selectedRobotId={selectedRobotId}
              onSelectRobot={handleSelectRobot}
              robotStates={robotStates}
              grid={grid}
              heatmapCells={heatmapCells}
              rows={rows}
              cols={cols}
              heatmapRows={heatmapRows}
              heatmapCols={heatmapCols}
            />
          )}
          {isLoadingSelectedRobot ? (
            <MainContentSkeleton />
          ) : (
          <>
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
                    obstacleCells={obstacleCells}
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
                    obstacleCells={obstacleCells}
                    pointCloud={pointCloud}
                    connected={connected}
                  />
                </div>
              )}
            </div>
          </section>

          <aside className="relative z-10 flex flex-col gap-4 overflow-y-auto overflow-x-hidden min-w-0 shrink-0 px-2 py-1">
            <SensorReadout state={state} liveStatus={{ hasData, connected, liveOpacity }} />
            <AnalyticsPanel rooms={rooms} />
            <Alerts rooms={rooms} />
          </aside>
          </>
          )}
        </main>
      ) : (
        <DashboardSkeleton />
      )}
    </div>
  )
}
