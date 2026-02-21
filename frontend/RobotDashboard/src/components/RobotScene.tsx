import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useMemo } from 'react'

const POINT_COUNT = 1500

function Robot() {
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

  return (
    <group>
      {/* Robot body - box */}
      <mesh position={[0, bodyHeight / 2, 0]}>
        <boxGeometry args={[bodyWidth, bodyHeight, bodyDepth]} />
        <meshStandardMaterial color="#2D2D2D" />
      </mesh>
      {/* 4 wheels - cylinders */}
      {wheelPositions.map((pos, i) => (
        <mesh key={i} position={pos} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[wheelRadius, wheelRadius, wheelWidth, 16]} />
          <meshStandardMaterial color="#191919" />
        </mesh>
      ))}
    </group>
  )
}

function PointCloud() {
  const positions = useMemo(() => {
    const pos = new Float32Array(POINT_COUNT * 3)
    for (let i = 0; i < POINT_COUNT; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 6
      pos[i * 3 + 1] = (Math.random() - 0.5) * 4
      pos[i * 3 + 2] = (Math.random() - 0.5) * 6
    }
    return pos
  }, [])

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
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

function Scene() {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
      <Robot />
      <PointCloud />
      <OrbitControls enableDamping dampingFactor={0.05} />
    </>
  )
}

export default function RobotScene() {
  return (
    <div className="w-full h-full min-h-[400px]">
      <Canvas
        camera={{ position: [3, 2, 3], fov: 50 }}
        gl={{ antialias: true }}
      >
        <Scene />
      </Canvas>
    </div>
  )
}
