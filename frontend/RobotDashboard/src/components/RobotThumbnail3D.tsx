import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useMemo } from 'react'
import * as THREE from 'three'

function CameraLookAt({ target }: { target: [number, number, number] }) {
  const { camera } = useThree()
  useFrame(() => {
    camera.lookAt(new THREE.Vector3(...target))
  })
  return null
}
function tempToColorHex(temp: number): number {
  const t = Math.max(17, Math.min(24, temp))
  const x = Math.pow((t - 17) / 7, 0.55)
  let r: number, g: number, b: number
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

const UNEXPLORED = 0x283240

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

interface Robot3DMiniProps {
  x: number
  y: number
  theta: number
}

function Robot3DMini({ x, y, theta }: Robot3DMiniProps) {
  const headingRad = theta + (3 * Math.PI) / 2
  return (
    <group position={[x, 0, y]} rotation={[0, -headingRad, 0]}>
      <mesh position={[0, bodyHeight / 2, 0]}>
        <boxGeometry args={[bodyWidth, bodyHeight, bodyDepth]} />
        <meshStandardMaterial color="#00d4aa" emissive="#00d4aa" emissiveIntensity={0.3} />
      </mesh>
      {wheelPositions.map((pos, i) => (
        <mesh key={i} position={pos} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[wheelRadius, wheelRadius, wheelWidth, 12]} />
          <meshStandardMaterial color="#191919" />
        </mesh>
      ))}
      <mesh position={[0, casterRadius / 2, wheelZ - 3 * casterRadius]}>
        <sphereGeometry args={[casterRadius, 8, 8]} />
        <meshStandardMaterial color="#FFFFFF" />
      </mesh>
      <mesh position={[0, casterRadius * 2, wheelZ - 3 * casterRadius]} rotation={[0, Math.PI / 2, 0]}>
        <cylinderGeometry args={[servoRadius, servoRadius, servoHeight, 8]} />
        <meshStandardMaterial color="#AAAAAA" />
      </mesh>
      <mesh position={[0, casterRadius * 2 + (servoHeight * 2) / 3, wheelZ - 2.5 * casterRadius]}>
        <boxGeometry args={[0.3, 0.1, 0.1]} />
        <meshStandardMaterial color="#2D2D2D" />
      </mesh>
    </group>
  )
}

interface ThumbnailFloorProps {
  cx: number
  cy: number
  grid: number[][]
  heatmapCells: Record<string, number>
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
  radius: number
}

function ThumbnailFloor({ cx, cy, grid, heatmapCells, rows, cols, heatmapRows, heatmapCols, radius }: ThumbnailFloorProps) {
  const subdivR = heatmapRows > rows ? Math.floor(heatmapRows / rows) : 1
  const subdivC = heatmapCols > cols ? Math.floor(heatmapCols / cols) : 1

  const cells = useMemo(() => {
    const out: { row: number; col: number; cell: number; color: number }[] = []
    const r0 = Math.max(0, Math.floor(cy - radius))
    const r1 = Math.min(rows - 1, Math.ceil(cy + radius))
    const c0 = Math.max(0, Math.floor(cx - radius))
    const c1 = Math.min(cols - 1, Math.ceil(cx + radius))
    for (let row = r0; row <= r1; row++) {
      for (let col = c0; col <= c1; col++) {
        const cell = grid[row]?.[col] ?? 0
        const color = cell === 0 ? 0x1a2332 : UNEXPLORED
        let tempColor = color
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
        if (temp != null && cell !== 0) tempColor = tempToColorHex(temp)
        out.push({ row, col, cell, color: tempColor })
      }
    }
    return out
  }, [cx, cy, grid, heatmapCells, rows, cols, heatmapRows, heatmapCols, radius])

  return (
    <group>
      {cells.map(({ row, col, cell, color }) => {
        const x = col + 0.5
        const z = row + 0.5
        if (cell === 0) return null
        return (
          <mesh key={`${row}-${col}`} position={[x, 0.001, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[1, 1]} />
            <meshBasicMaterial color={color} side={THREE.DoubleSide} />
          </mesh>
        )
      })}
    </group>
  )
}

interface RobotThumbnail3DProps {
  robotState: { position?: { x: number; y: number; theta?: number } } | null | undefined
  grid: number[][]
  heatmapCells: Record<string, number>
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
}

function ThumbnailScene({ robotState, grid, heatmapCells, rows, cols, heatmapRows, heatmapCols }: RobotThumbnail3DProps) {
  const pos = robotState?.position ?? { x: rows / 2, y: cols / 2, theta: 0 }
  const cx = pos.x
  const cy = pos.y
  const theta = pos.theta ?? 0

  return (
    <>
      <ambientLight intensity={1} />
      <directionalLight position={[5, 10, 5]} intensity={0.8} />
      <ThumbnailFloor
        cx={cx}
        cy={cy}
        grid={grid}
        heatmapCells={heatmapCells}
        rows={rows}
        cols={cols}
        heatmapRows={heatmapRows}
        heatmapCols={heatmapCols}
        radius={4}
      />
      <Robot3DMini x={cx} y={cy} theta={theta} />
    </>
  )
}

export default function RobotThumbnail3D(props: RobotThumbnail3DProps) {
  const pos = props.robotState?.position ?? { x: 9, y: 14, theta: 0 }
  const cx = pos.x
  const cy = pos.y

  return (
    <div className="w-full aspect-[4/3] bg-[#1a2332] rounded overflow-hidden">
      <Canvas
        orthographic
        camera={{
          position: [cx, 12, cy],
          zoom: 22,
          near: 0.1,
          far: 100,
        }}
        gl={{ antialias: false, alpha: false }}
        style={{ width: '100%', height: '100%' }}
      >
        <CameraLookAt target={[cx, 0, cy]} />
        <ThumbnailScene {...props} />
      </Canvas>
    </div>
  )
}
