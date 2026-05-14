interface Props {
  points:    number
  maxPoints: number
  color:     string
}

export function PointsBar({ points, maxPoints, color }: Props) {
  const pct = maxPoints > 0 ? Math.round((points / maxPoints) * 100) : 0
  return (
    <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  )
}
