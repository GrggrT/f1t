"use client"

import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { formatLapTime } from "@/lib/utils"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://192.168.0.114:8000"

interface PracticeLap {
  lap_number: number
  lap_time_ms: number
  sector1_ms: number
  sector2_ms: number
  sector3_ms: number
  tyre_compound: string
  valid: boolean
}

interface PracticeSession {
  id: number
  track_id: number
  track_name: string
  session_type: string
  total_laps: number
  best_lap_ms: number | null
  created_at: string
  ended_at: string | null
  laps?: PracticeLap[]
}

export default function PracticePage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [sessions, setSessions] = useState<PracticeSession[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<PracticeSession | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const userId = session?.user?.id ? Number(session.user.id) : undefined

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login")
    }
  }, [router, status])

  useEffect(() => {
    if (!userId) {
      return
    }

    fetch(`${API}/api/practice/sessions?web_user_id=${userId}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((payload) => setSessions(Array.isArray(payload) ? payload : []))
      .finally(() => setLoading(false))
  }, [userId])

  async function loadDetail(sessionRow: PracticeSession) {
    if (selected?.id === sessionRow.id) {
      setSelected(null)
      return
    }

    setDetailLoading(true)
    try {
      const response = await fetch(`${API}/api/practice/sessions/${sessionRow.id}`)
      if (response.ok) {
        setSelected(await response.json())
      }
    } finally {
      setDetailLoading(false)
    }
  }

  const groupedByTrack = useMemo(() => {
    const map = new Map<string, PracticeSession[]>()
    for (const sessionRow of sessions) {
      const key = sessionRow.track_name || `Track ${sessionRow.track_id}`
      if (!map.has(key)) {
        map.set(key, [])
      }
      map.get(key)?.push(sessionRow)
    }
    return map
  }, [sessions])

  const bestLap = Math.min(...sessions.filter((sessionRow) => Boolean(sessionRow.best_lap_ms)).map((sessionRow) => sessionRow.best_lap_ms ?? Number.POSITIVE_INFINITY))

  if (status === "loading" || loading) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка истории практики...</div>
  }

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">История практики</p>
            <h1 className="page-title">Приватные сессии, записанные лаунчером.</h1>
            <p className="page-copy">
              Практика относится к member-слою. Она намеренно отделена от публичной истории гонок и дает каждому пилоту
              приватный архив индивидуальной подготовки перед возвращением в сезонное соревнование.
            </p>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Охват</p>
            <p className="mt-3 text-2xl font-semibold text-text">{groupedByTrack.size} трасс</p>
            <p className="mt-2 text-sm text-muted">
              {sessions.length} сессий - {sessions.reduce((total, sessionRow) => total + sessionRow.total_laps, 0)} кругов записано
            </p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Сессии</p>
          <p className="stat-value mono-data">{sessions.length}</p>
          <p className="mt-2 text-sm text-muted">Заезды, записанные лаунчером</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Круги</p>
          <p className="stat-value mono-data">{sessions.reduce((total, sessionRow) => total + sessionRow.total_laps, 0)}</p>
          <p className="mt-2 text-sm text-muted">Всего записанных кругов практики</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Трассы</p>
          <p className="stat-value mono-data">{groupedByTrack.size}</p>
          <p className="mt-2 text-sm text-muted">Уникальные площадки практики</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Лучший круг</p>
          <p className="stat-value mono-data">{Number.isFinite(bestLap) ? formatLapTime(bestLap) : "--"}</p>
          <p className="mt-2 text-sm text-muted">Самый быстрый зафиксированный сольный эталон</p>
        </div>
      </section>

      {sessions.length === 0 ? (
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Данных по практике пока нет</p>
          <h2 className="mt-3 section-title">Запустите лаунчер в личном режиме, чтобы начать накапливать историю.</h2>
          <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
            Практические сессии записываются приватно и остаются в вашем member-кабинете, пока вы не решите перейти в
            соревновательный сезонный режим.
          </p>
        </section>
      ) : (
        Array.from(groupedByTrack.entries()).map(([trackName, trackSessions]) => (
          <section key={trackName} className="surface-panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-6 py-5">
              <div>
                <p className="eyebrow">Архив трассы</p>
                <h2 className="mt-2 section-title">{trackName}</h2>
              </div>
              <span className="data-pill">
                {trackSessions.length} сессий - {trackSessions.reduce((total, sessionRow) => total + sessionRow.total_laps, 0)} кругов
              </span>
            </div>
            <div className="space-y-3 p-6">
              {trackSessions
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                .map((sessionRow) => (
                  <div key={sessionRow.id} className="rounded-[16px] border border-border bg-surfaceAlt/60">
                    <button
                      onClick={() => loadDetail(sessionRow)}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surfaceAlt"
                    >
                      <div className="flex-1">
                        <p className="text-base font-semibold text-text">{sessionRow.session_type}</p>
                        <p className="mt-1 text-sm text-muted">
                          {new Date(sessionRow.created_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" })}
                          {" - "}
                          {new Date(sessionRow.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                      <span className="data-pill">{sessionRow.total_laps} кругов</span>
                      <span className="mono-data text-sm text-text">{sessionRow.best_lap_ms ? formatLapTime(sessionRow.best_lap_ms) : "--"}</span>
                    </button>

                    {selected?.id === sessionRow.id && selected.laps ? (
                      <div className="border-t border-border px-5 pb-5 pt-2">
                        {detailLoading ? <p className="py-6 text-sm text-muted">Загрузка деталей сессии...</p> : null}
                        <div className="overflow-x-auto">
                          <table className="data-table min-w-[720px]">
                            <thead>
                              <tr>
                                <th>Круг</th>
                                <th className="text-right">Время</th>
                                <th className="text-right">S1</th>
                                <th className="text-right">S2</th>
                                <th className="text-right">S3</th>
                                <th className="text-right">Шины</th>
                                <th className="text-right">Состояние</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selected.laps.map((lap) => {
                                const isBest = lap.lap_time_ms > 0 && lap.lap_time_ms === selected.best_lap_ms
                                return (
                                  <tr key={lap.lap_number} className={!lap.valid ? "opacity-50" : undefined}>
                                    <td className="mono-data text-muted">L{lap.lap_number}</td>
                                    <td className="text-right mono-data font-semibold text-text">{formatLapTime(lap.lap_time_ms)}</td>
                                    <td className="text-right mono-data text-muted">{formatLapTime(lap.sector1_ms)}</td>
                                    <td className="text-right mono-data text-muted">{formatLapTime(lap.sector2_ms)}</td>
                                    <td className="text-right mono-data text-muted">{formatLapTime(lap.sector3_ms)}</td>
                                    <td className="text-right text-sm text-muted">{lap.tyre_compound || "--"}</td>
                                    <td className="text-right text-sm text-muted">{isBest ? "Лучший круг" : lap.valid ? "Валидный" : "Невалидный"}</td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ))}
            </div>
          </section>
        ))
      )}
    </div>
  )
}
