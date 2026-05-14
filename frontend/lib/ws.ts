"use client"

import { useEffect, useRef, useState } from "react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

export type AgentState = "idle" | "waiting" | "qualifying" | "race" | "finished" | "uploaded"

export interface AgentStatus {
  state: AgentState
  track_id: number | null
  track_name: string | null
  label: string
}

export interface LiveSnapshotPayload {
  status?: unknown
  live?: unknown
  updated_at?: string | null
}

export function normalizeAgentStatusMessage(message: unknown): AgentStatus | null {
  if (!message || typeof message !== "object") {
    return null
  }

  const payload = message as Record<string, unknown>
  const state = typeof payload.state === "string" ? payload.state.toLowerCase() : null
  if (!state) {
    return null
  }

  return {
    state: state as AgentState,
    track_id: typeof payload.track_id === "number" ? payload.track_id : null,
    track_name: typeof payload.track_name === "string" ? payload.track_name : null,
    label: typeof payload.label === "string" ? payload.label : "",
  }
}

export async function fetchLiveSnapshot(signal?: AbortSignal): Promise<LiveSnapshotPayload | null> {
  try {
    const response = await fetch(`${API_BASE}/api/live/snapshot`, {
      cache: "no-store",
      signal,
    })
    if (!response.ok) {
      return null
    }
    return response.json()
  } catch {
    return null
  }
}

export function useAgentStatus(): AgentStatus | null {
  const [status, setStatus] = useState<AgentStatus | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let active = true
    const controller = new AbortController()

    async function hydrateFromSnapshot() {
      const snapshot = await fetchLiveSnapshot(controller.signal)
      if (!active || !snapshot?.status) {
        return
      }
      const nextStatus = normalizeAgentStatusMessage(snapshot.status)
      if (nextStatus) {
        setStatus(nextStatus)
      }
    }

    function connect() {
      if (!active) return
      const ws = new WebSocket(`${WS_BASE}/ws/client`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type !== "agent_status") {
            return
          }
          const nextStatus = normalizeAgentStatusMessage(message)
          if (nextStatus) {
            setStatus(nextStatus)
          }
        } catch {
          // Ignore malformed websocket events.
        }
      }

      ws.onclose = () => {
        if (active) {
          retryRef.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => ws.close()
    }

    void hydrateFromSnapshot()
    connect()
    pollRef.current = setInterval(() => {
      void hydrateFromSnapshot()
    }, 5000)

    return () => {
      active = false
      controller.abort()
      if (retryRef.current) clearTimeout(retryRef.current)
      if (pollRef.current) clearInterval(pollRef.current)
      wsRef.current?.close()
    }
  }, [])

  return status
}

export const STATE_COLORS: Record<AgentState, string> = {
  idle: "bg-gray-600",
  waiting: "bg-yellow-500",
  qualifying: "bg-blue-500",
  race: "bg-green-500",
  finished: "bg-orange-500",
  uploaded: "bg-emerald-500",
}

export const STATE_DOTS: Record<AgentState, string> = {
  idle: "idle",
  waiting: "waiting",
  qualifying: "qualifying",
  race: "race",
  finished: "finished",
  uploaded: "uploaded",
}
