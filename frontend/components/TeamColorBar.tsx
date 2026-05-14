interface Props {
  color: string
  className?: string
}

export function TeamColorBar({ color, className = "" }: Props) {
  return (
    <div
      className={`w-1 rounded-full shrink-0 ${className}`}
      style={{ backgroundColor: color }}
    />
  )
}
