"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { formatLapTime } from "@/lib/utils"
import { fetchLiveSnapshot, normalizeAgentStatusMessage, type AgentStatus } from "@/lib/ws"

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

interface LiveEntry {
  position: number
  driver_name: string
  team_name: string
  team_color: string
  is_human: boolean
  player_name?: string
  lap: number
  gap: string
  last_lap_ms: number | null
  best_lap_ms: number | null
  tyre: string
  pit_stops: number
  sector1_ms: number | null
  sector2_ms: number | null
  sector3_ms: number | null
  drs_active: boolean
}

function normalizeLiveEntries(message: unknown): LiveEntry[] | null {
  if (!message || typeof message !== "object") {
    return null
  }

  const payload = message as Record<string, unknown>
  if (Array.isArray(payload.entries)) {
    return payload.entries as LiveEntry[]
  }

  if (!payload.data || typeof payload.data !== "object") {
    return null
  }

  const nested = payload.data as Record<string, unknown>
  return Array.isArray(nested.entries) ? (nested.entries as LiveEntry[]) : null
}

function parseUpdatedAt(value: string | null | undefined): Date | null {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const STATE_THEME: Record<string, { chip: string; dot: string; copy: string }> = {
  idle: { chip: "bg-white/5 text-muted border-border", dot: "bg-gray-500", copy: "Активная гоночная сессия не обнаружена." },
  waiting: { chip: "bg-amber-500/10 text-amber-300 border-amber-500/20", dot: "bg-amber-400", copy: "Дирекция гонки подключена и ждет следующего перехода состояния." },
  qualifying: { chip: "bg-info/10 text-info border-info/20", dot: "bg-info", copy: "Квалификация активна. Обновления тайминга должны идти в реальном времени." },
    race: { chip: "bg-success/10 text-success border-success/20", dot: "bg-success", copy: "Гонка идет. Используйте этот экран как оперативную операторскую поверхность." },
  finished: { chip: "bg-amber-500/10 text-amber-300 border-amber-500/20", dot: "bg-amber-400", copy: "Сессия завершена и ждет архивации или загрузки." },
  uploaded: { chip: "bg-success/10 text-success border-success/20", dot: "bg-success", copy: "Телеметрия загружена, и история гонки уже должна быть доступна." },
}

const TYRE_TONE: Record<string, string> = {
  SOFT: "text-danger",
  MEDIUM: "text-amber",
  HARD: "text-text",
  INTER: "text-success",
  WET: "text-info",
  SUPER_SOFT: "text-danger",
}

export default function SeasonLivePage() {
  const [status, setStatus] = useState<AgentStatus | null>(null)
  const [entries, setEntries] = useState<LiveEntry[]>([])
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let active = true
    const controller = new AbortController()

    async function hydrateFromSnapshot() {
      const snapshot = await fetchLiveSnapshot(controller.signal)
      if (!active || !snapshot) {
        return
      }

      const nextStatus = normalizeAgentStatusMessage(snapshot.status)
      if (nextStatus) {
        setStatus(nextStatus)
      }

      const nextEntries = normalizeLiveEntries(snapshot.live)
      if (nextEntries) {
        setEntries(nextEntries)
      }

      const updatedAt = parseUpdatedAt(snapshot.updated_at)
      if (updatedAt) {
        setLastUpdate(updatedAt)
      }
    }

    function connect() {
      if (!active) {
        return
      }
      const ws = new WebSocket(`${WS_BASE}/ws/client`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (active) {
          retryRef.current = setTimeout(connect, 3000)
        }
      }
      ws.onerror = () => {
        setConnected(false)
        ws.close()
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === "agent_status") {
            const nextStatus = normalizeAgentStatusMessage(message)
            if (nextStatus) {
              setStatus(nextStatus)
            }
            setLastUpdate(new Date())
          }
          if (message.type === "live_data") {
            const nextEntries = normalizeLiveEntries(message)
            if (nextEntries) {
              setEntries(nextEntries)
              setLastUpdate(new Date())
            }
          }
        } catch {
          // Ignore malformed websocket events.
        }
      }
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

  const theme = STATE_THEME[status?.state ?? "idle"] ?? STATE_THEME.idle
  const isSessionLive = status?.state === "race" || status?.state === "qualifying"
  const leader = entries[0] ?? null
  const humans = useMemo(() => entries.filter((entry) => entry.is_human), [entries])

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
          <p className="eyebrow">Оперативное состояние гонки</p>
            <h1 className="page-title">Состояние гоночного вечера, читаемое как с pit wall.</h1>
            <p className="page-copy">
            Эта страница это оперативная ветка сезонной оболочки. Она держит на виду состояние подключения, режим
              события и текущий порядок еще до перехода в глубокую телеметрию или архивные детали.
            </p>
            <div className="flex flex-wrap gap-3">
              <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs uppercase tracking-[0.18em] ${theme.chip}`}>
                <span className={`h-2 w-2 rounded-full ${theme.dot}`} />
                {status?.label ?? "Ждем дирекцию гонки"}
              </span>
              <span className="data-pill">{connected ? "Websocket подключен" : "Websocket офлайн"}</span>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Текущая трасса</p>
            <p className="mt-3 text-2xl font-semibold text-text">{status?.track_name ?? "Нет активной трассы"}</p>
            <p className="mt-2 text-sm leading-6 text-muted">{theme.copy}</p>
            <p className="mt-4 text-xs text-muted">
              {lastUpdate
                ? `Последнее обновление ${lastUpdate.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
                    : "Ждем первый оперативный пакет"}
            </p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Состояние сессии</p>
          <p className="stat-value">{status?.state?.toUpperCase() ?? "IDLE"}</p>
          <p className="mt-2 text-sm text-muted">Live, ожидание или загрузка завершена</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Отслеживаемые пилоты</p>
          <p className="stat-value mono-data">{entries.length}</p>
              <p className="mt-2 text-sm text-muted">Машины, которые сейчас видны в оперативном потоке</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Пилоты-люди</p>
          <p className="stat-value mono-data">{humans.length}</p>
          <p className="mt-2 text-sm text-muted">Участники лиги, видимые в этой сессии</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Лидер</p>
          <p className="stat-value">{leader?.player_name ?? leader?.driver_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">
            {leader ? `Круг ${leader.lap} - ${leader.gap || "лидер"}` : "Ждем порядок пилотов"}
          </p>
        </div>
      </section>

      {!isSessionLive ? (
        <section className="surface-panel p-8 text-center sm:p-10">
          <div className="mx-auto max-w-[56ch] text-center">
            <p className="eyebrow">Нет активной сессии</p>
            <h2 className="mt-3 section-title">Сейчас в этом сезоне нет активной гонки.</h2>
            <p className="mx-auto mt-4 max-w-[48ch] text-sm leading-7 text-muted">
              Оперативная доска остается доступной как операторская контрольная точка. Когда дирекция гонки подключится снова, этот
              экран автоматически поднимет тайминг и живое состояние пилотов.
            </p>
          </div>
        </section>
      ) : null}

      {isSessionLive && entries.length > 0 ? (
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_320px]">
          <div className="surface-panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-6 py-5">
              <div>
                <p className="eyebrow">Текущий порядок</p>
            <h2 className="mt-2 section-title">Оперативный лидерборд</h2>
              </div>
              <span className="data-pill">Автообновление через websocket</span>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[860px]">
                <thead>
                  <tr>
                    <th>Поз</th>
                    <th>Пилот</th>
                    <th className="text-center">Tyre</th>
                    <th className="text-right">Круг</th>
                    <th className="text-right">Последний</th>
                    <th className="text-right">Лучший</th>
                    <th className="text-right">Питы</th>
                    <th className="text-right">Отрыв</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={`${entry.position}-${entry.driver_name}`} className={entry.is_human ? "player-row" : undefined}>
                      <td className="mono-data text-muted">P{entry.position}</td>
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-1 rounded-full" style={{ backgroundColor: entry.team_color }} />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-text">{entry.player_name ?? entry.driver_name}</span>
                              {entry.drs_active ? <span className="data-pill">DRS</span> : null}
                            </div>
                            <p className="mt-1 text-xs text-muted">{entry.team_name}</p>
                          </div>
                        </div>
                      </td>
                      <td className={`text-center text-xs font-medium uppercase ${TYRE_TONE[entry.tyre] ?? "text-muted"}`}>
                        {entry.tyre || "--"}
                      </td>
                      <td className="text-right mono-data text-muted">{entry.lap}</td>
                      <td className="text-right mono-data text-muted">{formatLapTime(entry.last_lap_ms)}</td>
                      <td className="text-right mono-data text-text">{formatLapTime(entry.best_lap_ms)}</td>
                      <td className="text-right mono-data text-muted">{entry.pit_stops}</td>
                      <td className="text-right mono-data text-muted">{entry.gap || "лидер"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-4">
            <div className="surface-panel p-5">
            <p className="eyebrow">Оперативный срез</p>
              <p className="mt-3 text-xl font-semibold text-text">{leader?.player_name ?? leader?.driver_name ?? "Лидера пока нет"}</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                {leader
                  ? `${leader.team_name} сейчас контролирует голову сессии на круге ${leader.lap}.`
                  : "Ждем достаточно телеметрии, чтобы определить лидеров пелотона."}
              </p>
            </div>

            <div className="surface-panel p-5">
              <p className="eyebrow">Заметки по сессии</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
                <li>Используйте этот экран, чтобы следить за порядком и свежестью данных во время гоночного вечера.</li>
                <li>После загрузки переходите в детали гонки за каноничным архивным результатом.</li>
              <li>Глубокая телеметрия должна жить в анализе и сравнении, а не в стартовом экране состояния.</li>
              </ul>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  )
}
