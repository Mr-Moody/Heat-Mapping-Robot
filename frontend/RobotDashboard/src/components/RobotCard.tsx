import RobotThumbnail3D from './RobotThumbnail3D'

export interface RobotInfo {
  id: string
  name: string
  active: boolean
  last_seen?: number | null
}

interface RobotCardProps {
  robot: RobotInfo
  selected: boolean
  robotState: { position?: { x: number; y: number; theta?: number } } | null | undefined
  grid: number[][]
  heatmapCells: Record<string, number>
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
  onSelect: () => void
}

export default function RobotCard({
  robot,
  selected,
  robotState,
  grid,
  heatmapCells,
  rows,
  cols,
  heatmapRows,
  heatmapCols,
  onSelect,
}: RobotCardProps) {
  const isActive = robot.active
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-lg border transition-all duration-150 overflow-hidden ${
        selected
          ? 'border-cyan-400 ring-1 ring-cyan-400/50 bg-[#1a2332]'
          : isActive
            ? 'border-uber-gray-light bg-[#1a2332]/80 hover:border-cyan-400/50'
            : 'border-uber-gray-light/60 bg-[#1a2332]/60 opacity-60 grayscale hover:opacity-80'
      }`}
    >
      <div className="p-1">
        <RobotThumbnail3D
          robotState={robotState}
          grid={grid}
          heatmapCells={heatmapCells}
          rows={rows}
          cols={cols}
          heatmapRows={heatmapRows}
          heatmapCols={heatmapCols}
        />
      </div>
      <div className="px-2 pb-2 pt-0">
        <span className="text-sm font-medium text-uber-gray-dark truncate block">
          {robot.name}
        </span>
      </div>
    </button>
  )
}
