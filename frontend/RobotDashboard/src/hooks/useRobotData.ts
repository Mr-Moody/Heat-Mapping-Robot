import { useState, useEffect } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws'

export interface RobotPose {
  x: number
  y: number
  heading_deg: number
}

export interface ThermalPoint {
  x_m: number
  y_m: number
  surface_temp_c: number
  air_temp_c: number
  room_id: number
  is_overheated: boolean
}

export interface AnalyticsSummary {
  wasted_power_w: number
  hot_zone_count: number
  max_temp_c: number
  avg_temp_c: number
  setpoint_c: number
  overheat_threshold_c: number
}

export interface RobotData {
  points: number[][]
  robot: RobotPose
  action: string
  sweep_cm: number[]
  thermal_points?: ThermalPoint[]
  analytics?: AnalyticsSummary
  air_temp_c?: number | null
  humidity_pct?: number | null
}

const defaultRobot: RobotPose = { x: 0, y: 0, heading_deg: 0 }

export function useRobotData() {
  const [data, setData] = useState<RobotData>({
    points: [],
    robot: defaultRobot,
    action: 'IDLE',
    sweep_cm: [],
    thermal_points: [],
  })
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimeout: ReturnType<typeof setTimeout>

    const connect = () => {
      ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        setConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as RobotData
          setData({
            points: msg.points ?? [],
            robot: msg.robot ?? defaultRobot,
            action: msg.action ?? 'IDLE',
            sweep_cm: msg.sweep_cm ?? [],
            thermal_points: msg.thermal_points ?? [],
            analytics: msg.analytics,
            air_temp_c: msg.air_temp_c ?? null,
            humidity_pct: msg.humidity_pct ?? null,
          })
        } catch {
          // Ignore parse errors
        }
      }

      ws.onclose = () => {
        setConnected(false)
        reconnectTimeout = setTimeout(connect, 2000)
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimeout)
      ws?.close()
    }
  }, [])

  return { ...data, connected }
}
