import { useState, useEffect } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws'

export interface RobotPose {
  x: number
  y: number
  heading_deg: number
}

export interface RobotData {
  points: number[][]
  robot: RobotPose
  action: string
  sweep_cm: number[]
}

const defaultRobot: RobotPose = { x: 0, y: 0, heading_deg: 0 }

export function useRobotData() {
  const [data, setData] = useState<RobotData>({
    points: [],
    robot: defaultRobot,
    action: 'IDLE',
    sweep_cm: [],
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
