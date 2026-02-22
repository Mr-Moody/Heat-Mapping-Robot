import RobotCard, { type RobotInfo } from './RobotCard'

interface RobotListPanelProps {
  robots: RobotInfo[]
  selectedRobotId: string | null
  onSelectRobot: (id: string) => void
  robotStates: Record<string, { position?: { x: number; y: number; theta?: number } } | null | undefined>
  grid: number[][]
  heatmapCells: Record<string, number>
  rows: number
  cols: number
  heatmapRows: number
  heatmapCols: number
}

export default function RobotListPanel({
  robots,
  selectedRobotId,
  onSelectRobot,
  robotStates,
  grid,
  heatmapCells,
  rows,
  cols,
  heatmapRows,
  heatmapCols,
}: RobotListPanelProps) {
  if (robots.length === 0) return null

  const sortedRobots = [...robots].sort((a, b) =>
    (a.name ?? a.id).localeCompare(b.name ?? b.id, undefined, { sensitivity: 'base' })
  )

  return (
    <aside className="flex flex-col gap-3 overflow-y-auto min-w-[200px] w-[200px] shrink-0 py-2">
      <h2 className="text-xs font-semibold text-uber-gray-mid px-2 uppercase tracking-wider">
        Robots
      </h2>
      {sortedRobots.map((robot) => (
        <RobotCard
          key={robot.id}
          robot={robot}
          selected={selectedRobotId === robot.id}
          robotState={robotStates[robot.id]}
          grid={grid}
          heatmapCells={heatmapCells}
          rows={rows}
          cols={cols}
          heatmapRows={heatmapRows}
          heatmapCols={heatmapCols}
          onSelect={() => onSelectRobot(robot.id)}
        />
      ))}
    </aside>
  )
}
