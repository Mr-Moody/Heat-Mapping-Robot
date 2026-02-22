import { Canvas } from '@react-three/fiber'
import { OrbitControls, Line } from '@react-three/drei'
import { useMemo, useRef, useLayoutEffect } from 'react'
import * as THREE from 'three'
import { tempToColorHex } from '../utils/heatmapColors'

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

const wheelPositions: [number, number, number][] = [
  [-wheelX, wheelRadius / 2, -wheelZ + wheelRadius],
  [wheelX, wheelRadius / 2, -wheelZ + wheelRadius],
]

interface Robot3DProps {
  x: number
  y: number
  theta: number
}

function Robot3D({ x, y, theta }: Robot3DProps) {
  const headingRad = theta + (3 * Math.PI) / 2
  return (
    <group position={[x, 0, y]} rotation={[0, -headingRad, 0]} scale={[0.5, 0.5, 0.5]}>
      <mesh position={[0, bodyHeight / 2, 0]}>
        <boxGeometry args={[bodyWidth, bodyHeight, bodyDepth]} />
        <meshStandardMaterial color="#00d4aa" emissive="#00d4aa" emissiveIntensity={0.3} />
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

const UNEXPLORED_COLOR = 0x283240

interface FloorGridProps {
  grid: number[][]
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
  heatmapCells: Record<string, number>
}

const cellSize = 1
const boxMatrix = new THREE.Matrix4()

function FloorGrid({ grid, rows, cols, heatmapRows = 0, heatmapCols = 0, heatmapCells = {} }: FloorGridProps) {
  const subdivR = heatmapRows > rows ? Math.floor(heatmapRows / rows) : 1
  const subdivC = heatmapCols > cols ? Math.floor(heatmapCols / cols) : 1

  const { boxCells, planeCells } = useMemo(() => {
    const boxes: { row: number; col: number }[] = []
    const planes: { row: number; col: number; color: number }[] = []
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const cell = grid[row]?.[col] ?? 0
        const baseColor = cell === 0 ? 0x1a2332 : UNEXPLORED_COLOR
        let tempColorVal = baseColor
        let sum = 0
        let n = 0
        for (let dr = 0; dr < subdivR; dr++) {
          for (let dc = 0; dc < subdivC; dc++) {
            const fr = row * subdivR + dr
            const fc = col * subdivC + dc
            const t = heatmapCells[`${fr},${fc}`]
            if (t != null) {
              sum += t
              n++
            }
          }
        }
        const temp = n > 0 ? sum / n : heatmapCells[`${row},${col}`]
        if (temp != null && cell !== 0) tempColorVal = tempToColorHex(temp)
        if (cell === 0) {
          boxes.push({ row, col })
        } else {
          planes.push({ row, col, color: tempColorVal })
        }
      }
    }
    return { boxCells: boxes, planeCells: planes }
  }, [grid, rows, cols, heatmapRows, heatmapCols, subdivR, subdivC, heatmapCells])

  const boxRef = useRef<THREE.InstancedMesh>(null)
  const boxGeo = useMemo(() => new THREE.BoxGeometry(cellSize, 0.5, cellSize), [])
  const boxMat = useMemo(() => new THREE.MeshStandardMaterial({ color: 0x1a2332 }), [])

  useLayoutEffect(() => {
    if (!boxRef.current || boxCells.length === 0) return
    boxCells.forEach(({ row, col }, i) => {
      const x = col * cellSize + cellSize / 2
      const z = row * cellSize + cellSize / 2
      boxMatrix.setPosition(x, 0.25, z)
      boxRef.current!.setMatrixAt(i, boxMatrix)
    })
    boxRef.current.instanceMatrix.needsUpdate = true
  }, [boxCells])

  if (boxCells.length === 0 && planeCells.length === 0) return null

  return (
    <group>
      {boxCells.length > 0 && (
        <instancedMesh ref={boxRef} args={[boxGeo, boxMat, boxCells.length]} frustumCulled={false} />
      )}
      {planeCells.map(({ row, col, color }) => {
        const x = col * cellSize + cellSize / 2
        const z = row * cellSize + cellSize / 2
        return (
          <mesh key={`${row}-${col}`} position={[x, 0.002, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[cellSize, cellSize]} />
            <meshStandardMaterial color={color} side={THREE.DoubleSide} />
          </mesh>
        )
      })}
    </group>
  )
}

interface TrailLineProps {
  trail: [number, number][] | null | undefined
}

function TrailLine({ trail }: TrailLineProps) {
  const points = useMemo(() => {
    if (!trail || trail.length < 2) return []
    return trail.map(([x, y]) => [x, 0.02, y] as [number, number, number])
  }, [trail])
  if (points.length < 2) return null
  return <Line points={points} color="#00d4aa" />
}

interface HeatmapPoint {
  x: number
  y: number
  z: number
  color: number
}

interface ObstacleCuboidsProps {
  cells: [number, number][]
}

const obstacleMatrix = new THREE.Matrix4()

function ObstacleCuboids({ cells }: ObstacleCuboidsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const halfCellSize = 0.5
  const height = 0.5
  const obstacleGeo = useMemo(() => new THREE.BoxGeometry(halfCellSize, height, halfCellSize), [])
  const obstacleMat = useMemo(() => new THREE.MeshStandardMaterial({ color: 0x000000 }), [])

  useLayoutEffect(() => {
    if (!meshRef.current || !cells?.length) return
    cells.forEach(([row, col], i) => {
      obstacleMatrix.setPosition(col + 0.5, height / 2, row + 0.5)
      meshRef.current!.setMatrixAt(i, obstacleMatrix)
    })
    meshRef.current.instanceMatrix.needsUpdate = true
  }, [cells])

  if (!cells || cells.length === 0) return null
  return (
    <instancedMesh ref={meshRef} args={[obstacleGeo, obstacleMat, cells.length]} frustumCulled={false} />
  )
}

interface ObstaclePointCloudProps {
  points: number[][]
}

function ObstaclePointCloud({ points }: ObstaclePointCloudProps) {
  if (!points || points.length === 0) return null
  const positions = useMemo(() => {
    const arr = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      arr[i * 3] = p[0]
      arr[i * 3 + 1] = p[1]
      arr[i * 3 + 2] = p[2]
    })
    return arr
  }, [points])
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.08} color="#ff6b6b" sizeAttenuation />
    </points>
  )
}

interface SimulatedPointCloudProps {
  points: number[][]
}

function SimulatedPointCloud({ points }: SimulatedPointCloudProps) {
  if (!points || points.length === 0) return null
  const positions = useMemo(() => {
    const arr = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      arr[i * 3] = p[0]
      arr[i * 3 + 1] = p[1]
      arr[i * 3 + 2] = p[2]
    })
    return arr
  }, [points])
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.06} color="#00d4aa" sizeAttenuation opacity={0.85} transparent />
    </points>
  )
}

interface ThermalPointCloudProps {
  heatmapPoints: HeatmapPoint[]
}

function ThermalPointCloud({ heatmapPoints }: ThermalPointCloudProps) {
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
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.15} vertexColors sizeAttenuation />
    </points>
  )
}

interface Scene3DProps {
  state: { position?: { x: number; y: number; theta?: number } } | null | undefined
  trail: [number, number][] | null | undefined
  grid: number[][]
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
  heatmapCells: Record<string, number>
  obstaclePoints: number[][]
  obstacleCells: [number, number][]
  pointCloud: number[][]
}

function Scene3D({ state, trail, grid, rows, cols, heatmapRows, heatmapCols, heatmapCells = {}, obstaclePoints = [], obstacleCells = [], pointCloud = [] }: Scene3DProps) {
  const heatmapPoints = useMemo(() => {
    const pts: HeatmapPoint[] = []
    if (!trail || trail.length === 0) return pts
    const subdivR = heatmapRows > rows ? Math.floor(heatmapRows / rows) : 1
    const subdivC = heatmapCols > cols ? Math.floor(heatmapCols / cols) : 1
    const seen = new Set<string>()
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
          if (t != null) {
            sum += t
            n++
          }
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
      <ambientLight intensity={1.1} />
      <directionalLight position={[10, 20, 10]} intensity={1.3} castShadow />
      <directionalLight position={[-8, 10, -5]} intensity={0.5} />
      <directionalLight position={[0, 20, 0]} intensity={0.3} />
      <FloorGrid
        grid={grid}
        rows={rows}
        cols={cols}
        heatmapRows={heatmapRows}
        heatmapCols={heatmapCols}
        heatmapCells={heatmapCells}
      />
      <Robot3D x={robotPos.x} y={robotPos.y} theta={robotPos.theta ?? 0} />
      <TrailLine trail={trail} />
      <ThermalPointCloud heatmapPoints={heatmapPoints} />
      <SimulatedPointCloud points={pointCloud} />
      <ObstacleCuboids cells={obstacleCells} />
      <ObstaclePointCloud points={obstaclePoints} />
      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        minDistance={5}
        maxDistance={50}
        target={[robotPos.x || cols / 2, 0, robotPos.y || rows / 2]}
      />
    </>
  )
}

interface RobotState {
  position?: { x: number; y: number; theta?: number }
  ultrasonic_distance_cm?: number
  temperature_c?: number
  humidity_percent?: number
}

interface RobotScene3DProps {
  state: RobotState | null | undefined
  trail?: [number, number][] | null
  grid?: number[][]
  rows?: number
  cols?: number
  heatmapRows?: number
  heatmapCols?: number
  heatmapCells?: Record<string, number>
  obstaclePoints?: number[][]
  obstacleCells?: [number, number][]
  pointCloud?: number[][]
  connected?: boolean
}

export default function RobotScene3D({
  state,
  trail,
  grid = [],
  rows = 9,
  cols = 19,
  heatmapRows = 0,
  heatmapCols = 0,
  heatmapCells = {},
  obstaclePoints = [],
  obstacleCells = [],
  pointCloud = [],
  connected,
}: RobotScene3DProps) {
  const r = rows || 9
  const c = cols || 19
  return (
    <div className="relative w-full h-[450px] min-h-[450px] bg-[#0f1419] [&_canvas]:block [&_canvas]:w-full [&_canvas]:h-full [&_canvas]:min-h-[450px]">
      {!connected && !state?.position && (
        <div className="absolute top-3 left-3 right-3 z-10 text-center text-sm text-uber-gray-mid bg-[rgba(26,35,50,0.9)] py-2 px-3 rounded">
          Connecting...
        </div>
      )}
      {connected && !state?.position && (
        <div className="absolute top-3 left-3 right-3 z-10 text-center text-sm text-uber-gray-mid bg-[rgba(26,35,50,0.9)] py-2 px-3 rounded">
          Waiting for robot data...
        </div>
      )}
      {state && (
        <div className="absolute bottom-3 left-3 z-10 flex flex-col gap-2">
          <div className="flex gap-4 text-xs font-mono text-cyan-400 bg-[rgba(26,35,50,0.9)] py-1.5 px-2.5 rounded">
            <span>Ultrasonic: {state.ultrasonic_distance_cm?.toFixed(0) ?? '—'} cm</span>
            <span>Temp: {state.temperature_c?.toFixed(1) ?? '—'} °C</span>
            <span>Humidity: {state.humidity_percent?.toFixed(0) ?? '—'} %</span>
          </div>
          {(pointCloud.length > 0 || obstaclePoints.length > 0) && (
            <div className="text-xs text-uber-gray-mid bg-[rgba(26,35,50,0.9)] py-1 px-2 rounded flex flex-row items-center gap-3">
              {pointCloud.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full bg-[#00d4aa]" />
                  SLAM environment ({pointCloud.length})
                </span>
              )}
              {obstaclePoints.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full bg-[#ff6b6b]" />
                  SLAM obstacles ({obstaclePoints.length})
                </span>
              )}
            </div>
          )}
        </div>
      )}
      <Canvas
        camera={{ position: [c / 2 + 3, 12, r / 2 + 3], fov: 45 }}
        gl={{ antialias: true }}
      >
        <Scene3D
          state={state}
          trail={trail ?? null}
          grid={grid}
          rows={r}
          cols={c}
          heatmapRows={heatmapRows}
          heatmapCols={heatmapCols}
          heatmapCells={heatmapCells}
          obstaclePoints={obstaclePoints}
          obstacleCells={obstacleCells}
          pointCloud={pointCloud}
        />
      </Canvas>
    </div>
  )
}
