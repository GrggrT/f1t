"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { useEffect, useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface WebMe {
  id: number
  is_system_admin: boolean
}

interface Player {
  id: number
  name: string
  telegram_id: number | null
  steam_names: string[]
  steam_id64: string | null
  steam_url: string | null
  avatar_url: string | null
}

interface SeasonRow {
  id: number
  name: string
  status: string
  races_played: number
  total_rounds: number
}

function EditPlayerRow({ player, onSaved }: { player: Player; onSaved: (player: Player) => void }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(player.name)
  const [steamRaw, setSteamRaw] = useState(player.steam_names.join(", "))
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      const response = await fetch(`${API}/api/players/${player.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, steam_names: steamRaw.split(",").map((entry) => entry.trim()).filter(Boolean) }),
      })
      if (response.ok) {
        onSaved(await response.json())
        setEditing(false)
      }
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <tr>
        <td className="mono-data text-muted">#{player.id}</td>
        <td>
          <div className="flex items-center gap-3">
            {player.avatar_url ? (
              <img src={player.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover" />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surfaceAlt text-xs text-muted">?</div>
            )}
            <span className="font-medium text-text">{player.name}</span>
          </div>
        </td>
        <td className="mono-data text-muted">{player.telegram_id ?? "--"}</td>
        <td className="text-sm text-muted">{player.steam_names.join(", ") || "--"}</td>
        <td className="text-right">
          <button onClick={() => setEditing(true)} className="text-sm text-info transition-colors hover:text-text">
            Изменить
          </button>
        </td>
      </tr>
    )
  }

  return (
    <tr>
      <td className="mono-data text-muted">#{player.id}</td>
      <td>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="h-10 w-full rounded-[10px] border border-border bg-[#0f141a] px-3 text-sm text-text outline-none transition-colors focus:border-borderStrong"
        />
      </td>
      <td className="mono-data text-muted">{player.telegram_id ?? "--"}</td>
      <td>
        <input
          value={steamRaw}
          onChange={(event) => setSteamRaw(event.target.value)}
          placeholder="Имена Steam через запятую"
          className="h-10 w-full rounded-[10px] border border-border bg-[#0f141a] px-3 text-sm text-text outline-none transition-colors focus:border-borderStrong"
        />
      </td>
      <td>
        <div className="flex justify-end gap-2">
          <button onClick={save} disabled={saving} className="ui-button-secondary h-10 px-3">
            {saving ? "Сохраняем..." : "Сохранить"}
          </button>
          <button
            onClick={() => {
              setEditing(false)
              setName(player.name)
              setSteamRaw(player.steam_names.join(", "))
            }}
            className="ui-button-tertiary"
          >
            Отмена
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function SystemAdminPage() {
  const { data: session, status } = useSession()
  const [me, setMe] = useState<WebMe | null>(null)
  const [players, setPlayers] = useState<Player[]>([])
  const [seasons, setSeasons] = useState<SeasonRow[]>([])
  const [tab, setTab] = useState<"players" | "seasons">("players")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

  function notify(text: string, ok = true) {
    setMessage({ text, ok })
    window.clearTimeout((notify as typeof notify & { timeout?: number }).timeout)
    ;(notify as typeof notify & { timeout?: number }).timeout = window.setTimeout(() => setMessage(null), 4000)
  }

  useEffect(() => {
    const userId = session?.user?.id ? Number(session.user.id) : undefined
    if (!userId) {
      return
    }

    fetch(`${API}/api/web/me/${userId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setMe)
      .catch(() => {})
  }, [session?.user?.id])

  useEffect(() => {
    if (!me?.is_system_admin) {
      return
    }

    Promise.all([
      fetch(`${API}/api/players`).then((response) => (response.ok ? response.json() : [])),
      fetch(`${API}/api/seasons`).then((response) => (response.ok ? response.json() : [])),
    ])
      .then(([nextPlayers, nextSeasons]) => {
        setPlayers(nextPlayers)
        setSeasons(nextSeasons)
      })
      .catch(() => {})
  }, [me?.is_system_admin])

  async function generateContracts(seasonId: number) {
    setLoading(true)
    try {
      const response = await fetch(`${API}/api/contracts/generate/${seasonId}`, { method: "POST" })
      const payload = await response.json()
      notify(payload.message ?? "Контракты сгенерированы.")
    } catch {
      notify("Не удалось сгенерировать контракты.", false)
    } finally {
      setLoading(false)
    }
  }

  if (status === "loading") {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка системной админки...</div>
  }

  if (!session) {
    return (
      <section className="surface-panel p-8 text-center sm:p-10">
        <p className="eyebrow">Системная админка</p>
        <h1 className="mt-3 section-title">Сначала войдите, затем открывайте операторский backend.</h1>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/login" className="ui-button-primary">
            Войти
          </Link>
          <Link href="/workspace" className="ui-button-tertiary">
            Назад в кабинет
          </Link>
        </div>
      </section>
    )
  }

  if (!me?.is_system_admin) {
    return (
      <section className="surface-panel p-8 text-center sm:p-10">
        <p className="eyebrow">Системная админка</p>
        <h1 className="mt-3 section-title">Эта консоль доступна только системным администраторам.</h1>
        <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
          Операторы сезона работают внутри своих страниц управления сезоном. Глобальная идентичность игроков и
          общеcистемное обслуживание сезонов живут здесь.
        </p>
      </section>
    )
  }

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Системная админка</p>
            <h1 className="page-title">Глобальная идентичность и обслуживание сезонов вне публичной оболочки.</h1>
            <p className="page-copy">
              Этот слой намеренно отделен от страниц сезона и кабинетов участников. Используйте его для нормализации
              идентичности игроков и общесистемного обслуживания сезонов, а не для операторских действий в гоночный вечер.
            </p>
            <div className="flex flex-wrap gap-3">
              <button onClick={() => setTab("players")} className={tab === "players" ? "ui-button-secondary" : "ui-button-tertiary"}>
                Игроки
              </button>
              <button onClick={() => setTab("seasons")} className={tab === "seasons" ? "ui-button-secondary" : "ui-button-tertiary"}>
                Сезоны
              </button>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Системный охват</p>
            <p className="mt-3 text-2xl font-semibold text-text">Глобальный backend</p>
            <p className="mt-2 text-sm text-muted">{players.length} игроков - {seasons.length} сезонов в индексе</p>
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
          <p className="stat-label">Игроки</p>
          <p className="stat-value mono-data">{players.length}</p>
          <p className="mt-2 text-sm text-muted">Каноничные идентичности пилотов</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Сезоны</p>
          <p className="stat-value mono-data">{seasons.length}</p>
          <p className="mt-2 text-sm text-muted">Записи чемпионатов</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Активные сезоны</p>
          <p className="stat-value mono-data">{seasons.filter((season) => season.status === "active").length}</p>
          <p className="mt-2 text-sm text-muted">Сейчас активные чемпионаты</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Архивные гонки</p>
          <p className="stat-value mono-data">{seasons.reduce((total, season) => total + season.races_played, 0)}</p>
          <p className="mt-2 text-sm text-muted">Загруженные результаты гонок по всей системе</p>
        </div>
      </section>

      {tab === "players" ? (
        <section className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Идентичности игроков</p>
            <h2 className="mt-2 section-title">Каноничные имена, Telegram id и алиасы Steam.</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[820px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Игрок</th>
                  <th>Telegram</th>
                  <th>Алиасы Steam</th>
                  <th className="text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {players.map((player) => (
                  <EditPlayerRow
                    key={player.id}
                    player={player}
                    onSaved={(savedPlayer) => setPlayers((current) => current.map((entry) => (entry.id === savedPlayer.id ? savedPlayer : entry)))}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === "seasons" ? (
        <section className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Обслуживание сезонов</p>
            <h2 className="mt-2 section-title">Открывайте сезоны и запускайте глобальные задачи обслуживания.</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[760px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Сезон</th>
                  <th>Статус</th>
                  <th className="text-right">Этапы</th>
                  <th className="text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {seasons.map((season) => (
                  <tr key={season.id}>
                    <td className="mono-data text-muted">#{season.id}</td>
                    <td>
                      <Link href={`/season/${season.id}`} className="font-medium text-text transition-colors hover:text-accent">
                        {season.name}
                      </Link>
                    </td>
                    <td className="text-sm text-muted">{season.status}</td>
                    <td className="text-right mono-data text-muted">
                      {season.races_played}/{season.total_rounds}
                    </td>
                    <td>
                      <div className="flex justify-end gap-2">
                        {/* "Управление" link hidden — see PR 1.2.5; manage page is stubbed. */}
                        <button onClick={() => generateContracts(season.id)} disabled={loading} className="ui-button-secondary h-10 px-3">
                          Контракты
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
