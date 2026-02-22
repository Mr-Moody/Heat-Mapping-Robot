import { Canvas } from '@react-three/fiber'
import './RobotScene3D.css'
import { OrbitControls, Line } from '@react-three/drei'
import { useMemo } from 'react'
import * as THREE from 'three'

// Robot model dimensions (from RobotDashboard)
const wheelRadius = 0.16
const wheelWidth = 0.08
const casterRadius = 0.06
const bodyWidth = 0.5
const bodyHeight = 0.12
const bodyDepth = 0.6
const wheelX = bodyWidth / 2 + wheelWidth / 2
const wheelZ = bodyDepth / 2 + wheelWidth / 2
const servoHeight = 0.2
const servoRadius = 0.04

const wheelPositions = [
  [-wheelX, wheelRadius / 2, -wheelZ + wheelRadius],
  [wheelX, wheelRadius / 2, -wheelZ + wheelRadius],
]

function Robot3D({ x, y, theta }) {
  const headingRad = theta + (3 * Math.PI) / 2
  return (
    <group position={[x, 0, y]} rotation={[0, -headingRad, 0]}>
      <mesh position={[0, bodyHeight / 2, 0]}>
        <boxGeometry args={[bodyWidth, bodyHeight, bodyDepth]} />
        <meshStandardMaterial color="#00d4aa" emissive="#003d30" />
      </mesh>
      {wheelPositions.map((pos, i) => (
        <mesh key={i} position={pos} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[wheelRadius, wheelRadius, wheelWidth, 16]} />
          <meshStandardMaterial color="#191919" />
        </mesh>
      ))}
      <mesh position={[0, casterRadius / 2, wheelZ - 3 * casterRadius]}>
        <sphereGeometry args={[casterRadius, 16, 16]} />
        <meshStandardMaterial color="#FFFFFF" />
      </mesh>
      <mesh position={[0, casterRadius * 2, wheelZ - 3 * casterRadius]} rotation={[0, Math.PI / 2, 0]}>
        <cylinderGeometry args={[servoRadius, servoRadius, servoHeight, 16]} />
        <meshStandardMaterial color="#AAAAAA" />
      </mesh>
      <mesh position={[0, casterRadius * 2 + (servoHeight * 2) / 3, wheelZ - 2.5 * casterRadius]}>
        <boxGeometry args={[0.3, 0.1, 0.1]} />
        <meshStandardMaterial color="#2D2D2D" />
      </mesh>
    </group>
  )
}

// Same 17–24°C sensitive gradient as 2D heatmap
function tempToColorHex(temp) {
  const t = Math.max(17, Math.min(24, temp))
  const x = Math.pow((t - 17) / 7, 0.55)
  let r, g, b
  if (x <= 0.33) {
    const s = x / 0.33
    r = Math.round(25 + (110 - 25) * s)
    g = Math.round(120 + (195 - 120) * s)
    b = Math.round(70 + (55 - 70) * s)
  } else if (x <= 0.66) {
    const s = (x - 0.33) / 0.33
    r = Math.round(110 + (255 - 110) * s)
    g = Math.round(195 + (200 - 195) * s)
    b = Math.round(55 + (45 - 55) * s)
  } else {
    const s = (x - 0.66) / 0.34
    r = 255
    g = Math.round(200 + (70 - 200) * s)
    b = Math.round(45 + (38 - 45) * s)
  }
  return (r << 16) | (g << 8) | b
}

const UNEXPLORED_COLOR = 0x283240

function FloorGrid({ grid, rows, cols, heatmapRows = 0, heatmapCols = 0, heatmapCells = {} }) {
  const cellSize = 1
  const subdivR = heatmapRows > rows ? Math.floor(heatmapRows / rows) : 1
  const subdivC = heatmapCols > cols ? Math.floor(heatmapCols / cols) : 1

  const cells = useMemo(() => {
    const out = []
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const cell = grid[row]?.[col] ?? 0
        const color = cell === 0 ? 0x1a2332 : UNEXPLORED_COLOR
        let tempColor = color
        let sum = 0
        let n = 0
        for (let dr = 0; dr < subdivR; dr++) {
          for (let dc = 0; dc < subdivC; dc++) {
            const fr = row * subdivR + dr
            const fc = col * subdivC + dc
            const t = heatmapCells[`${fr},${fc}`]
            if (t != null) { sum += t; n++ }
          }
        }
        const temp = n > 0 ? sum / n : heatmapCells[`${row},${col}`]
        if (temp != null && cell !== 0) tempColor = tempToColorHex(temp)
        out.push({
          row,
          col,
          cell,
          color: tempColor,
        })
      }
    }
    return out
  }, [grid, rows, cols, heatmapRows, heatmapCols, subdivR, subdivC, heatmapCells])

  return (
    <group>
      {cells.map(({ row, col, cell, color }) => {
        const x = col * cellSize + cellSize / 2
        const z = row * cellSize + cellSize / 2
        if (cell === 0) {
          return (
            <mesh key={`${row}-${col}`} position={[x, 0.25, z]}>
              <boxGeometry args={[cellSize, 0.5, cellSize]} />
              <meshStandardMaterial color={0x1a2332} />
            </mesh>
          )
        }
        return (
          <mesh key={`${row}-${col}`} position={[x, 0, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[cellSize, cellSize]} />
            <meshStandardMaterial color={color} />
          </mesh>
        )
      })}
    </group>
  )
}

function TrailLine({ trail }) {
  const points = useMemo(() => {
    if (!trail || trail.length < 2) return []
    return trail.map(([x, y]) => [x, 0.02, y])
  }, [trail])
  if (points.length < 2) return null
  return <Line points={points} color="#00d4aa" />
}

function ThermalPointCloud({ heatmapPoints }) {
  if (!heatmapPoints || heatmapPoints.length === 0) return null
  const positions = new Float32Array(heatmapPoints.length * 3)
  const colors = new Float32Array(heatmapPoints.length * 3)
  heatmapPoints.forEach((p, i) => {
    positions[i * 3] = p.x
    positions[i * 3 + 1] = p.y
    positions[i * 3 + 2] = p.z
    const hex = p.color
    colors[i * 3] = ((hex >> 16) & 255) / 255
    colors[i * 3 + 1] = ((hex >> 8) & 255) / 255
    colors[i * 3 + 2] = (hex & 255) / 255
  })
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={heatmapPoints.length} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={heatmapPoints.length} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial size={0.15} vertexColors sizeAttenuation />
    </points>
  )
}

function Scene3D({ state, trail, grid, rows, cols, heatmapRows, heatmapCols, heatmapCells = {} }) {
  const heatmapPoints = useMemo(() => {
    const pts = []
    if (!trail || trail.length === 0) return pts
    const subdivR = heatmapRows > rows ? Math.floor(heatmapRows / rows) : 1
    const subdivC = heatmapCols > cols ? Math.floor(heatmapCols / cols) : 1
    const seen = new Set()
    for (const [x, y] of trail) {
      const col = Math.floor(x)
      const row = Math.floor(y)
      const key = `${row},${col}`
      if (seen.has(key)) continue
      seen.add(key)
      const cell = grid[row]?.[col] ?? 0
      let sum = 0
      let n = 0
      for (let dr = 0; dr < subdivR; dr++) {
        for (let dc = 0; dc < subdivC; dc++) {
          const t = heatmapCells[`${row * subdivR + dr},${col * subdivC + dc}`]
          if (t != null) { sum += t; n++ }
        }
      }
      const temp = n > 0 ? sum / n : heatmapCells[key]
      if (temp != null && cell !== 0) {
        pts.push({
          x: col + 0.5,
          y: 0.08 + (temp - 17) * 0.02,
          z: row + 0.5,
          color: tempToColorHex(temp),
        })
      }
    }
    return pts
  }, [trail, grid, heatmapRows, heatmapCols, rows, cols, heatmapCells])

  const robotPos = state?.position ?? { x: 0, y: 0, theta: 0 }

  return (
    <>
      <ambientLight intensity={0.9} />
      <directionalLight position={[10, 15, 10]} intensity={1.2} castShadow />
      <directionalLight position={[-8, 10, -5]} intensity={0.5} />
      <directionalLight position={[0, 20, 0]} intensity={0.3} />
      <FloorGrid grid={grid} rows={rows} cols={cols} heatmapRows={heatmapRows} heatmapCols={heatmapCols} heatmapCells={heatmapCells} />
      <Robot3D x={robotPos.x} y={robotPos.y} theta={robotPos.theta ?? 0} />
      <TrailLine trail={trail} />
      <ThermalPointCloud heatmapPoints={heatmapPoints} />
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={3}
        maxDistance={40}
        target={[cols / 2, 0, rows / 2]}
      />
    </>
  )
}

export default function RobotScene3D({ state, trail, grid = [], rows = 9, cols = 19, heatmapRows = 0, heatmapCols = 0, heatmapCells = {}, connected }) {
  const r = rows || 9
  const c = cols || 19
  return (
    <div className="robot-scene-3d">
      {!connected && (
        <div className="robot-scene-overlay">Connecting...</div>
      )}
      {connected && !state?.position && (
        <div className="robot-scene-overlay">Waiting for robot data...</div>
      )}
      {state && (
        <div className="robot-scene-sensors">
          <span>Ultrasonic: {state.ultrasonic_distance_cm?.toFixed(0) ?? '—'} cm</span>
          <span>Temp: {state.temperature_c?.toFixed(1) ?? '—'} °C</span>
          <span>Humidity: {state.humidity_percent?.toFixed(0) ?? '—'} %</span>
        </div>
      )}
      <Canvas
        camera={{ position: [c / 2 + 5, 8, r / 2 + 5], fov: 50 }}
        gl={{ antialias: true }}
      >
        <Scene3D state={state} trail={trail} grid={grid} rows={r} cols={c} heatmapRows={heatmapRows} heatmapCols={heatmapCols} heatmapCells={heatmapCells} />
      </Canvas>
    </div>
  )
}
