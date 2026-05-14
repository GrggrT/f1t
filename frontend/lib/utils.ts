export function formatLapTime(ms: number | null): string {
  if (!ms) return "--"
  const totalSeconds = ms / 1000
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = (totalSeconds % 60).toFixed(3).padStart(6, "0")
  return minutes > 0 ? `${minutes}:${seconds}` : `${seconds}s`
}

export function formatRaceTime(seconds: number | null): string {
  if (!seconds) return "--"
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remaining = (seconds % 60).toFixed(3)
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${remaining.padStart(6, "0")}`
  return `${minutes}:${remaining.padStart(6, "0")}`
}

export function formatDate(iso: string | null): string {
  if (!iso) return "--"
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" })
}

export function positionSuffix(position: number): string {
  if (position === 1) return "1st"
  if (position === 2) return "2nd"
  if (position === 3) return "3rd"
  return `${position}th`
}

export const SEASON_ID = 1
