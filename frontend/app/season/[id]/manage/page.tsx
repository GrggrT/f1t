"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { useEffect, useMemo, useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

const F1_2025_ORDER = [0, 2, 13, 3, 29, 30, 27, 5, 4, 6, 17, 7, 10, 9, 26, 11, 20, 12, 15, 19, 16, 31, 32, 14]

interface LobbyInfo {
  id: number
  name: string
  status: string
  creator_id: number | null
  creator_name: string | null
  moderators: { web_user_id: number; name: string }[]
  races_played: number
  total_rounds: number
  your_role: "admin" | "moderator" | "member" | "guest"
}

interface Track {
  id: number
  name: string
  gp: string
}

interface CalendarEntry {
  round: number
  track_id: number
  track_name: string
}

function AccessDenied() {
  return (
    <section className="surface-panel p-8 text-center sm:p-10">
      <p className="eyebrow">Операторский слой</p>
      <h1 className="mt-3 section-title">Этот кабинет доступен только операторам сезона.</h1>
      <p className="mx-auto mt-4 max-w-[48ch] text-sm leading-7 text-muted">
        Только владелец сезона и назначенные модераторы могут менять настройки, пересобирать календарь и управлять операторами.
      </p>
    </section>
  )
}

export default function ManagePage({ params }: { params: { id: string } }) {
  const seasonId = Number(params.id)
  const { data: session } = useSession()
  const userId = (session?.user as { id?: number } | undefined)?.id

  const [info, setInfo] = useState<LobbyInfo | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [calendar, setCalendar] = useState<CalendarEntry[]>([])
  const [tab, setTab] = useState<"general" | "calendar" | "moderators">("general")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

  const [seasonName, setSeasonName] = useState("")
  const [statusValue, setStatusValue] = useState("active")
  const [trackSearch, setTrackSearch] = useState("")
  const [moderatorId, setModeratorId] = useState("")

  function notify(text: string, ok = true) {
    setMessage({ text, ok })
    window.clearTimeout((notify as typeof notify & { timeout?: number }).timeout)
    ;(notify as typeof notify & { timeout?: number }).timeout = window.setTimeout(() => setMessage(null), 4500)
  }

  useEffect(() => {
    if (!userId) {
      return
    }

    Promise.all([
      fetch(`${API}/api/lobby/${seasonId}/info?web_user_id=${userId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/seasons/${seasonId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/admin/tracks`).then((response) => (response.ok ? response.json() : [])),
    ]).then(([nextInfo, season, nextTracks]) => {
      if (nextInfo) {
        setInfo(nextInfo)
        setSeasonName(nextInfo.name)
        setStatusValue(nextInfo.status)
      }
      if (season?.calendar) {
        setCalendar(season.calendar)
      }
      setTracks(nextTracks)
    })
  }, [seasonId, userId])

  async function claimOwnership() {
    if (!userId) {
      return
    }

    const response = await fetch(`${API}/api/lobby/${seasonId}/claim?web_user_id=${userId}`, { method: "POST" })
    const payload = await response.json()

    if (response.ok) {
      notify(payload.message ?? "Владение закреплено.")
      window.location.reload()
      return
    }

    notify(payload.detail ?? "Не удалось закрепить владение.", false)
  }

  async function saveGeneral() {
    if (!userId) {
      return
    }

    setLoading(true)
    const response = await fetch(`${API}/api/lobby/${seasonId}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requester_id: userId, name: seasonName, status: statusValue }),
    })
    const payload = await response.json()
    setLoading(false)

    if (response.ok) {
      notify("Настройки сезона сохранены.")
      return
    }

    notify(payload.detail ?? "Не удалось сохранить настройки.", false)
  }

  async function saveCalendar() {
    if (!userId) {
      return
    }

    setLoading(true)
    const response = await fetch(`${API}/api/lobby/${seasonId}/calendar`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requester_id: userId, entries: calendar }),
    })
    const payload = await response.json()
    setLoading(false)

    if (response.ok) {
      notify(`Календарь сохранен: ${payload.rounds ?? calendar.length} этапов.`)
      return
    }

    notify(payload.detail ?? "Не удалось сохранить календарь.", false)
  }

  async function addModerator() {
    if (!userId || !moderatorId) {
      return
    }

    const parsedId = Number(moderatorId)
    if (Number.isNaN(parsedId)) {
      notify("Введите числовой system user id.", false)
      return
    }

    const response = await fetch(`${API}/api/lobby/${seasonId}/moderators`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ web_user_id: parsedId, requester_id: userId }),
    })
    const payload = await response.json()

    if (response.ok) {
      setInfo((current) =>
        current
          ? { ...current, moderators: [...current.moderators, { web_user_id: parsedId, name: payload.name }] }
          : current,
      )
      setModeratorId("")
      notify(`${payload.name} добавлен как модератор.`)
      return
    }

    notify(payload.detail ?? "Не удалось добавить модератора.", false)
  }

  async function removeModerator(webUserId: number) {
    if (!userId) {
      return
    }

    const response = await fetch(`${API}/api/lobby/${seasonId}/moderators/${webUserId}?requester_id=${userId}`, {
      method: "DELETE",
    })

    if (response.ok) {
      setInfo((current) =>
        current ? { ...current, moderators: current.moderators.filter((moderator) => moderator.web_user_id !== webUserId) } : current,
      )
      notify("Модератор удален.")
      return
    }

    notify("Не удалось удалить модератора.", false)
  }

  function addTrack(track: Track) {
    if (calendar.some((entry) => entry.track_id === track.id)) {
      return
    }
    setCalendar((current) => [...current, { round: current.length + 1, track_id: track.id, track_name: track.name }])
  }

  function removeTrack(index: number) {
    setCalendar((current) =>
      current
        .filter((_, currentIndex) => currentIndex !== index)
        .map((entry, currentIndex) => ({ ...entry, round: currentIndex + 1 })),
    )
  }

  function moveTrack(index: number, direction: -1 | 1) {
    setCalendar((current) => {
      const nextIndex = index + direction
      if (nextIndex < 0 || nextIndex >= current.length) {
        return current
      }
      const next = [...current]
      ;[next[index], next[nextIndex]] = [next[nextIndex], next[index]]
      return next.map((entry, currentIndex) => ({ ...entry, round: currentIndex + 1 }))
    })
  }

  function applyPreset() {
    const trackMap = new Map(tracks.map((track) => [track.id, track]))
    const preset = F1_2025_ORDER.map((trackId, index) => {
      const track = trackMap.get(trackId)
      return track ? { round: index + 1, track_id: trackId, track_name: track.name } : null
    }).filter(Boolean) as CalendarEntry[]
    setCalendar(preset)
  }

  const isAdmin = info?.your_role === "admin"
  const usedTrackIds = new Set(calendar.map((entry) => entry.track_id))
  const availableTracks = useMemo(
    () =>
      tracks.filter(
        (track) =>
          !usedTrackIds.has(track.id) &&
          (trackSearch === "" || track.name.toLowerCase().includes(trackSearch.toLowerCase()) || track.gp.toLowerCase().includes(trackSearch.toLowerCase())),
      ),
    [trackSearch, tracks, usedTrackIds],
  )

  if (!session) {
    return (
      <section className="surface-panel p-8 text-center sm:p-10">
        <p className="eyebrow">Операторский слой</p>
        <h1 className="mt-3 section-title">Сначала войдите, потом открывайте операции сезона.</h1>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/login" className="ui-button-primary">
            Войти
          </Link>
          <Link href={`/season/${seasonId}`} className="ui-button-tertiary">
            Назад к сезону
          </Link>
        </div>
      </section>
    )
  }

  if (!info) {
    return <div className="py-20 text-center text-sm text-muted">Загрузка состояния оператора сезона...</div>
  }

  if (info.creator_id === null) {
    return (
      <section className="surface-panel p-8 text-center sm:p-10">
        <p className="eyebrow">Сезон без владельца</p>
        <h1 className="mt-3 section-title">У этого сезона пока нет владельца.</h1>
        <p className="mx-auto mt-4 max-w-[48ch] text-sm leading-7 text-muted">
          Закрепите владение, чтобы открыть настройки, назначение операторов и управление календарем этого чемпионата.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button onClick={claimOwnership} className="ui-button-primary">
            Закрепить владение
          </button>
          <Link href={`/season/${seasonId}`} className="ui-button-tertiary">
            Назад к сезону
          </Link>
        </div>
      </section>
    )
  }

  if (info.your_role === "guest" || info.your_role === "member") {
    return <AccessDenied />
  }

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Оператор сезона</p>
            <h1 className="page-title">Операторские контролы остаются отделенными от публичной оболочки сезона.</h1>
            <p className="page-copy">
              Эта консоль отвечает за конфигурацию, обслуживание календаря и назначение модераторов. Она намеренно скрыта
              от публичного продуктового слоя, чтобы операторские действия гоночного вечера не протекали в страницы каталога и открытия.
            </p>
            <div className="flex flex-wrap gap-3">
              <button onClick={() => setTab("general")} className={tab === "general" ? "ui-button-secondary" : "ui-button-tertiary"}>
                Общие
              </button>
              <button onClick={() => setTab("calendar")} className={tab === "calendar" ? "ui-button-secondary" : "ui-button-tertiary"}>
                Календарь
              </button>
              {isAdmin ? (
                <button onClick={() => setTab("moderators")} className={tab === "moderators" ? "ui-button-secondary" : "ui-button-tertiary"}>
                  Модераторы
                </button>
              ) : null}
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние оператора</p>
            <p className="mt-3 text-2xl font-semibold text-text">{info.name}</p>
            <p className="mt-2 text-sm text-muted">
              {info.your_role === "admin" ? "Владелец сезона" : "Модератор"} - {info.races_played}/{info.total_rounds} этапов завершено
            </p>
            <p className="mt-4 text-xs text-muted">Владелец: {info.creator_name ?? "Неизвестно"}</p>
          </div>
        </div>
      </section>

      {message ? (
        <div className={`rounded-[12px] border px-4 py-3 text-sm ${message.ok ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger"}`}>
          {message.text}
        </div>
      ) : null}

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Роль</p>
          <p className="stat-value">{info.your_role === "admin" ? "Владелец" : "Модератор"}</p>
          <p className="mt-2 text-sm text-muted">Уровень доступа в этом сезоне</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Статус</p>
          <p className="stat-value">{statusValue}</p>
          <p className="mt-2 text-sm text-muted">Маркер жизненного цикла сезона</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Этапы</p>
          <p className="stat-value mono-data">
            {info.races_played}/{Math.max(info.total_rounds, calendar.length)}
          </p>
          <p className="mt-2 text-sm text-muted">Завершено против настроенного</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Модераторы</p>
          <p className="stat-value mono-data">{info.moderators.length}</p>
          <p className="mt-2 text-sm text-muted">Назначенные операторские аккаунты</p>
        </div>
      </section>

      {tab === "general" ? (
        <section className="surface-panel p-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-5">
              <div>
                <p className="eyebrow">Общие настройки</p>
                <h2 className="mt-2 section-title">Идентичность сезона и состояние жизненного цикла.</h2>
              </div>
              <div className="grid gap-4">
                <div>
                  <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-dim">Название сезона</label>
                  <input
                    value={seasonName}
                    onChange={(event) => setSeasonName(event.target.value)}
                    className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-dim">Жизненный цикл</label>
                  <select
                    value={statusValue}
                    onChange={(event) => setStatusValue(event.target.value)}
                    className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                  >
                    <option value="active">active</option>
                    <option value="finished">finished</option>
                    <option value="archived">archived</option>
                  </select>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <button onClick={saveGeneral} disabled={loading} className="ui-button-primary">
                  {loading ? "Сохраняем..." : "Сохранить настройки"}
                </button>
                <Link href={`/season/${seasonId}`} className="ui-button-tertiary">
                  Открыть публичный сезон
                </Link>
              </div>
            </div>

            <div className="surface-panel-muted p-5">
              <p className="eyebrow">Заметки оператору</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
                <li>Используйте `active`, пока еще ожидаются загрузки после гоночных вечеров.</li>
                <li>Переводите в `finished`, когда чемпионат завершен, но еще считается текущим.</li>
                <li>Архивируйте только тогда, когда сезон должен вести себя как чистая история.</li>
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      {tab === "calendar" ? (
        <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <div className="surface-panel overflow-hidden">
            <div className="border-b border-border px-6 py-5">
              <p className="eyebrow">Пул трасс</p>
              <h2 className="mt-2 section-title">Добавляйте этапы в сезонный таймлайн.</h2>
            </div>
            <div className="p-6">
              <div className="flex flex-wrap gap-3">
                <button onClick={applyPreset} className="ui-button-secondary">
                  Применить пресет F1 2025
                </button>
              </div>
              <div className="mt-4">
                <input
                  value={trackSearch}
                  onChange={(event) => setTrackSearch(event.target.value)}
                  placeholder="Фильтр по трассам или гран-при..."
                  className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                />
              </div>
              <div className="mt-4 max-h-[420px] space-y-2 overflow-y-auto">
                {availableTracks.map((track) => (
                  <button
                    key={track.id}
                    onClick={() => addTrack(track)}
                    className="w-full rounded-[12px] border border-border bg-surfaceAlt/70 px-4 py-3 text-left transition-colors hover:border-borderStrong hover:bg-surfaceAlt"
                  >
                    <p className="font-medium text-text">{track.name}</p>
                    <p className="mt-1 text-xs text-muted">{track.gp}</p>
                  </button>
                ))}
                {availableTracks.length === 0 ? <p className="text-sm text-muted">Ни одна трасса не подходит под текущий фильтр.</p> : null}
              </div>
            </div>
          </div>

          <div className="surface-panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-6 py-5">
              <div>
                <p className="eyebrow">Настроенный календарь</p>
                <h2 className="mt-2 section-title">Выстройте сезон раунд за раундом.</h2>
              </div>
              <button onClick={saveCalendar} disabled={loading || calendar.length === 0} className="ui-button-primary">
                {loading ? "Сохраняем..." : `Сохранить ${calendar.length} этапов`}
              </button>
            </div>
            <div className="space-y-3 p-6">
              {calendar.length === 0 ? (
                <div className="surface-panel-muted p-5">
                  <p className="text-sm text-muted">Этапы пока не настроены. Добавьте трассы из левой колонки, чтобы собрать таймлайн сезона.</p>
                </div>
              ) : null}

              {calendar.map((entry, index) => (
                <div key={`${entry.track_id}-${entry.round}`} className="archive-row md:grid-cols-[96px_minmax(0,1fr)_220px]">
                  <div>
                    <p className="utility-kicker">Раунд</p>
                    <p className="mt-2 mono-data text-lg text-muted">R{entry.round}</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-text">{entry.track_name}</p>
                    <p className="mt-2 text-sm text-muted">Порядок гонок в таймлайне чемпионата под контролем оператора.</p>
                  </div>
                  <div className="flex items-center justify-between gap-2 md:justify-end">
                    <button onClick={() => moveTrack(index, -1)} disabled={index === 0} className="ui-button-tertiary disabled:opacity-40">
                      Вверх
                    </button>
                    <button onClick={() => moveTrack(index, 1)} disabled={index === calendar.length - 1} className="ui-button-tertiary disabled:opacity-40">
                      Вниз
                    </button>
                    <button onClick={() => removeTrack(index)} className="ui-button-tertiary text-danger hover:text-danger">
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {tab === "moderators" && isAdmin ? (
        <section className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="surface-panel p-6">
            <p className="eyebrow">Назначить оператора</p>
            <h2 className="mt-2 section-title">Добавьте модератора по system user id.</h2>
            <p className="mt-4 text-sm leading-7 text-muted">
              Модераторы могут обслуживать календарь сезона и общие настройки, не забирая владение всей лигой.
            </p>
            <div className="mt-5 flex gap-3">
              <input
                value={moderatorId}
                onChange={(event) => setModeratorId(event.target.value)}
                placeholder="System user id"
                className="h-12 flex-1 rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
              />
              <button onClick={addModerator} disabled={!moderatorId} className="ui-button-primary">
                Добавить
              </button>
            </div>
          </div>

          <div className="surface-panel overflow-hidden">
            <div className="border-b border-border px-6 py-5">
              <p className="eyebrow">Текущие операторы</p>
              <h2 className="mt-2 section-title">Список активных модераторов.</h2>
            </div>
            <div className="space-y-3 p-6">
              {info.moderators.length === 0 ? (
                <div className="surface-panel-muted p-5">
                  <p className="text-sm text-muted">Модераторы пока не назначены.</p>
                </div>
              ) : null}
              {info.moderators.map((moderator) => (
                <div key={moderator.web_user_id} className="archive-row md:grid-cols-[minmax(0,1fr)_180px]">
                  <div>
                    <p className="text-lg font-semibold text-text">{moderator.name}</p>
                    <p className="mt-2 text-sm text-muted">System user #{moderator.web_user_id}</p>
                  </div>
                  <div className="flex items-center justify-between gap-3 md:justify-end">
                    <span className="data-pill">Модератор</span>
                    <button onClick={() => removeModerator(moderator.web_user_id)} className="text-sm text-danger transition-colors hover:text-text">
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  )
}
