import RobotScene from '../components/RobotScene'

export default function DashboardPage() {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[calc(100vh-4rem)] p-4 sm:p-6">
      <div className="w-full max-w-5xl h-[min(70vh,600px)] rounded-sm overflow-hidden bg-uber-gray-dark/5 border border-uber-gray-light/20">
        <RobotScene />
      </div>
    </div>
  )
}
