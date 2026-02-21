import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useRef, useMemo, useEffect } from 'react'
import * as THREE from 'three'
import { useRobotData } from '../hooks/useRobotData'

const wheelRadius = 0.15
const wheelWidth = 0.1
const bodyWidth = 1
const bodyHeight = 0.5
const bodyDepth = 0.5
const wheelX = bodyWidth / 2 + wheelWidth / 2
const wheelZ = bodyDepth / 2 + wheelWidth / 2

const wheelPositions: [number, number, number][] = [
  [-wheelX, wheelRadius, wheelZ],
  [wheelX, wheelRadius, wheelZ],
  [-wheelX, wheelRadius, -wheelZ],
  [wheelX, wheelRadius, -wheelZ],
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
        <mesh key={i} position={pos} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[wheelRadius, wheelRadius, wheelWidth, 16]} />
          <meshStandardMaterial color="#191919" />
        </mesh>
      ))}
    </group>
  )
}

interface PointCloudProps {
  points: number[][]
}

function PointCloud({ points }: PointCloudProps) {
  const pointsRef = useRef<THREE.Points>(null)

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

  const initialPositions = useMemo(() => {
    const arr = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      arr[i * 3] = p[0]
      arr[i * 3 + 1] = p[1]
      arr[i * 3 + 2] = p[2]
    })
    return arr
  }, [points])

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[initialPositions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.02}
        color={0x000000}
        sizeAttenuation
      />
    </points>
  )
}

interface SceneProps {
  points: number[][]
  robot: { x: number; y: number; heading_deg: number }
}

function Scene({ points, robot }: SceneProps) {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
      <Robot x={robot.x} y={robot.y} heading_deg={robot.heading_deg} />
      <PointCloud points={points} />
      <OrbitControls enableDamping dampingFactor={0.05} />
    </>
  )
}

export default function RobotScene() {
  const { points, robot, action, connected, analytics } = useRobotData()

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
          <div className="absolute top-4 left-4 z-10 text-xs text-uber-gray-mid bg-uber-white/80 px-2 py-1 rounded">
            {action}
          </div>
          {analytics && (
            <div className="absolute top-4 right-4 z-10 text-xs bg-uber-white/90 px-2 py-1.5 rounded shadow-sm">
              <div className="font-medium text-uber-gray-dark">Thermal analytics</div>
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
        <Scene points={points} robot={robot} />
      </Canvas>
    </div>
  )
}
