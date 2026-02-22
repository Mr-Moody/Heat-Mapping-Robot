import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useRef, useMemo, useEffect } from 'react'
import * as THREE from 'three'
import { useRobotData } from '../hooks/useRobotData'

const NO_DATA = -999

function tempToColor(t: number): [number, number, number] {
  if (t <= NO_DATA + 1) return [0.2, 0.2, 0.2]
  const cold = 15, mild = 20, warm = 25, hot = 30
  if (t < cold) return [0, 0, 0.8]
  if (t < mild) return [0, 0.5 + (t - cold) / (mild - cold) * 0.5, 0.8]
  if (t < warm) return [(t - mild) / (warm - mild) * 1, 1, 0.2]
  if (t < hot) return [1, 1 - (t - warm) / (hot - warm) * 0.5, 0]
  return [1, 0.2, 0]
}

function gridToDataTexture(
  grid: number[][],
  colorFn: (v: number) => [number, number, number]
): THREE.DataTexture {
  const rows = grid.length
  const cols = grid[0]?.length ?? 0
  const data = new Uint8Array(cols * rows * 4)
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const v = grid[i]?.[j] ?? 0
      const [r, g, b] = colorFn(v)
      const idx = (i * cols + j) * 4
      data[idx] = Math.round(r * 255)
      data[idx + 1] = Math.round(g * 255)
      data[idx + 2] = Math.round(b * 255)
      data[idx + 3] = v <= NO_DATA + 1 ? 0 : 200
    }
  }
  const tex = new THREE.DataTexture(data, cols, rows)
  tex.needsUpdate = true
  tex.flipY = true
  return tex
}

// Robot model: 1/2 scale, units in metres (matches point cloud: distance_cm/100)
const SCALE = 0.25
const wheelRadius = 0.16 * SCALE
const wheelWidth = 0.08 * SCALE
const casterRadius = 0.06 * SCALE
const bodyWidth = 0.5 * SCALE
const bodyHeight = 0.12 * SCALE
const bodyDepth = 0.6 * SCALE
const wheelX = bodyWidth / 2 + wheelWidth / 2
const wheelZ = bodyDepth / 2 + wheelWidth / 2

const servoHeight = 0.2 * SCALE
const servoRadius = 0.04 * SCALE

// Two wheels at the back (negative Z)
const wheelPositions: [number, number, number][] = [
  [-wheelX, wheelRadius/2, -wheelZ + wheelRadius],
  [wheelX, wheelRadius/2, -wheelZ + wheelRadius],
]

interface RobotProps {
  x: number
  y: number
  heading_deg: number
}

function Robot({ x, y, heading_deg }: RobotProps) {
  return (
    <group position={[x, 0, y]} rotation={[0, -((heading_deg * Math.PI) / 180), 0]}>
      <mesh position={[0, bodyHeight / 2, 0]}>
        <boxGeometry args={[bodyWidth, bodyHeight, bodyDepth]} />
        <meshStandardMaterial color="#2D2D2D" />
      </mesh>
      {wheelPositions.map((pos, i) => (
        <mesh key={i} position={pos} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[wheelRadius, wheelRadius, wheelWidth, 16]} />
          <meshStandardMaterial color="#191919" />
        </mesh>
      ))}
      <mesh position={[0, casterRadius/2, wheelZ - 3*casterRadius]}>
        <sphereGeometry args={[casterRadius, 16, 16]} />
        <meshStandardMaterial color="#FFFFFF" />
      </mesh>
      <mesh  position={[0, casterRadius*2, wheelZ - 3*casterRadius]} rotation={[0, Math.PI / 2, 0]}>
          <cylinderGeometry args={[servoRadius, servoRadius, servoHeight, 16]} />
          <meshStandardMaterial color="#AAAAAA" />
      </mesh>
      <mesh position={[0, casterRadius*2 + servoHeight * 2 / 3, wheelZ - 2.5*casterRadius]}>
        <boxGeometry args={[0.3 * SCALE, 0.1 * SCALE, 0.1 * SCALE]} />
        <meshStandardMaterial color="#2D2D2D" />
      </mesh>
    </group>
  )
}

interface PointCloudProps {
  points: number[][]
}

function PointCloud({ points }: PointCloudProps) {
  const pointsRef = useRef<THREE.Points>(null)

  const initialPositions = useMemo(() => {
    const arr = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      arr[i * 3] = p[0]
      arr[i * 3 + 1] = p[1]
      arr[i * 3 + 2] = p[2]
    })
    return arr
  }, [points])

  useEffect(() => {
    if (!pointsRef.current || points.length === 0) return

    const geom = pointsRef.current.geometry
    const positions = new Float32Array(points.length * 3)

    points.forEach((p, i) => {
      positions[i * 3] = p[0]
      positions[i * 3 + 1] = p[1]
      positions[i * 3 + 2] = p[2]
    })

    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geom.attributes.position.needsUpdate = true
  }, [points])

  if (points.length === 0) {
    return null
  }

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[initialPositions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.01}
        color={0x000000}
        sizeAttenuation
      />
    </points>
  )
}

interface ThermalOverlayProps {
  grid: number[][] | null | undefined
  bounds: [number, number, number, number] | null | undefined
}

function ThermalGroundOverlay({ grid, bounds }: ThermalOverlayProps) {
  const tex = useMemo(() => {
    if (!grid?.length || !bounds) return null
    return gridToDataTexture(grid, tempToColor)
  }, [grid, bounds])

  useEffect(() => () => tex?.dispose(), [tex])

  if (!tex || !bounds) return null
  const [xMin, xMax, yMin, yMax] = bounds
  const width = xMax - xMin
  const depth = yMax - yMin
  const cx = (xMin + xMax) / 2
  const cz = (yMin + yMax) / 2

  return (
    <mesh position={[cx, 0.001, cz]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[width, depth]} />
      <meshBasicMaterial
        map={tex}
        transparent
        opacity={0.75}
        depthWrite={false}
      />
    </mesh>
  )
}

interface OccupancyOverlayProps {
  grid: number[][] | null | undefined
  bounds: [number, number, number, number] | null | undefined
}

function OccupancyGroundOverlay({ grid, bounds }: OccupancyOverlayProps) {
  const tex = useMemo(() => {
    if (!grid?.length || !bounds) return null
    return gridToDataTexture(grid, (p) => {
      const v = 1 - p
      return [v, v, v]
    })
  }, [grid, bounds])

  useEffect(() => () => tex?.dispose(), [tex])

  if (!tex || !bounds) return null
  const [xMin, xMax, yMin, yMax] = bounds
  const width = xMax - xMin
  const depth = yMax - yMin
  const cx = (xMin + xMax) / 2
  const cz = (yMin + yMax) / 2

  return (
    <mesh position={[cx, 0.0005, cz]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[width, depth]} />
      <meshBasicMaterial
        map={tex}
        transparent
        opacity={0.4}
        depthWrite={false}
      />
    </mesh>
  )
}

interface SceneProps {
  points: number[][]
  robot: { x: number; y: number; heading_deg: number }
  thermalGrid?: number[][] | null
  thermalBounds?: [number, number, number, number] | null
  occupancyGrid?: number[][] | null
  occupancyBounds?: [number, number, number, number] | null
}

function Scene({ points, robot, thermalGrid, thermalBounds, occupancyGrid, occupancyBounds }: SceneProps) {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
      <OccupancyGroundOverlay grid={occupancyGrid} bounds={occupancyBounds} />
      <ThermalGroundOverlay grid={thermalGrid} bounds={thermalBounds} />
      <Robot x={robot.x} y={robot.y} heading_deg={robot.heading_deg} />
      <PointCloud points={points} />
      <OrbitControls enableDamping dampingFactor={0.05} />
    </>
  )
}

export default function RobotScene() {
  const {
    points, robot, action, connected, analytics, air_temp_c, humidity_pct,
    thermal_grid, thermal_grid_bounds, occupancy_grid, occupancy_bounds,
  } = useRobotData()

  return (
    <div className="w-full h-full min-h-[400px] relative">
      {!connected && (
        <div className="absolute top-4 left-4 right-4 z-10 text-center text-sm text-uber-gray-mid bg-uber-white/80 py-2 rounded">
          Connecting to backend...
        </div>
      )}
      {connected && points.length === 0 && (
        <div className="absolute top-4 left-4 right-4 z-10 text-center text-sm text-uber-gray-mid bg-uber-white/80 py-2 rounded">
          Waiting for data from Arduino... (run with SIMULATE=1 for demo)
        </div>
      )}
      {connected && points.length > 0 && (
        <>
          <div className="absolute top-4 left-4 z-10 text-xs text-uber-gray-mid bg-uber-white/80 px-2 py-1 rounded space-y-1">
            <div>{action}</div>
            {(air_temp_c != null || humidity_pct != null) && (
              <div className="text-uber-gray-dark">
                {air_temp_c != null && <span>{air_temp_c.toFixed(1)}°C</span>}
                {air_temp_c != null && humidity_pct != null && ' · '}
                {humidity_pct != null && <span>{humidity_pct.toFixed(0)}% RH</span>}
              </div>
            )}
          </div>
          {analytics && (
            <div className="absolute top-4 right-4 z-10 text-xs bg-uber-white/90 px-2 py-1.5 rounded shadow-sm">
              <div className="font-medium text-uber-gray-dark">Thermal analytics</div>
              <div>
                Current: {air_temp_c != null ? `${air_temp_c.toFixed(1)}°C` : '— (run dht_test to verify sensor)'}
              </div>
              <div>Wasted: {analytics.wasted_power_w.toFixed(0)} W</div>
              <div>Hot zones: {analytics.hot_zone_count}</div>
              <div>Max: {analytics.max_temp_c.toFixed(1)}°C | Avg: {analytics.avg_temp_c.toFixed(1)}°C</div>
            </div>
          )}
        </>
      )}
      <Canvas
        camera={{ position: [3, 2, 3], fov: 50 }}
        gl={{ antialias: true }}
      >
        <Scene
          points={points}
          robot={robot}
          thermalGrid={thermal_grid}
          thermalBounds={thermal_grid_bounds ?? undefined}
          occupancyGrid={occupancy_grid}
          occupancyBounds={occupancy_bounds ?? undefined}
        />
      </Canvas>
    </div>
  )
}
