"use client"

import { useAgentStatus, STATE_COLORS } from "@/lib/ws"

export function AgentStatusBadge() {
  const status = useAgentStatus()

  if (!status) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-muted">
        <span className="h-2 w-2 animate-pulse rounded-full bg-gray-600" />
        Agent offline
      </div>
    )
  }

  const dotColor = STATE_COLORS[status.state] ?? "bg-gray-600"

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${dotColor} ${status.state === "race" ? "animate-pulse" : ""}`} />
      <span className="font-medium text-text">{status.label}</span>
      {status.track_name ? <span className="text-muted">- {status.track_name}</span> : null}
    </div>
  )
}
