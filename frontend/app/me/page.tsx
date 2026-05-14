"use client"

import Link from "next/link"
import { signOut, useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface WebMe {
  id: number
  name: string
  email: string | null
  picture: string | null
  steam_id64: string | null
  player_id: number | null
  is_system_admin: boolean
  player?: {
    id: number
    name: string
    steam_url: string | null
    telegram_id: number | null
    steam_names: string[]
    avatar_url: string | null
  }
}

interface PlayerStats {
  total_points: number
  races: number
  wins: number
  podiums: number
  dnfs: number
  fastest_laps: number
  avg_position: number | null
  best_finish: number | null
  race_history: {
    race_id: number
    round: number | null
    track_name: string | null
    position: number | null
    points: number
    team_name: string
  }[]
}

interface FullProfile {
  rating: { rating: number; peak_rating: number; races_rated: number }
  season_history: {
    season_id: number
    season_name: string
    status: string
    position: number | null
    points: number
    wins: number
    podiums: number
    fastest_laps: number
    dnfs: number
    team_name: string | null
  }[]
  achievements: {
    code: string
    name: string
    description: string
    icon: string
    unlocked_at: string | null
  }[]
}

interface LobbyItem {
  id: number
  name: string
  members: number
  seasons: number
  your_role?: string
}

interface PlayerOption {
  id: number
  name: string
}

function ratingTier(rating: number) {
  if (rating >= 2000) return "Грандмастер"
  if (rating >= 1800) return "Мастер"
  if (rating >= 1600) return "Алмаз"
  if (rating >= 1400) return "Золото"
  if (rating >= 1200) return "Серебро"
  return "Бронза"
}

export default function MePage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [me, setMe] = useState<WebMe | null>(null)
  const [stats, setStats] = useState<PlayerStats | null>(null)
  const [profile, setProfile] = useState<FullProfile | null>(null)
  const [players, setPlayers] = useState<PlayerOption[]>([])
  const [linkId, setLinkId] = useState("")
  const [linking, setLinking] = useState(false)
  const [linkMessage, setLinkMessage] = useState<string | null>(null)
  const [question, setQuestion] = useState("")
  const [assistantAnswer, setAssistantAnswer] = useState<string | null>(null)
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [lobbies, setLobbies] = useState<LobbyItem[]>([])
  const [newLobbyName, setNewLobbyName] = useState("")
  const [creatingLobby, setCreatingLobby] = useState(false)

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login")
    }
  }, [router, status])

  useEffect(() => {
    const userId = session?.user?.id ? Number(session.user.id) : undefined
    if (!userId) {
      return
    }

    fetch(`${API}/api/web/me/${userId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(async (payload: WebMe | null) => {
        setMe(payload)

        if (payload?.player_id) {
          const [statsResponse, profileResponse] = await Promise.all([
            fetch(`${API}/api/player/${payload.player_id}/stats`),
            fetch(`${API}/api/player/${payload.player_id}/full-profile`),
          ])

          if (statsResponse.ok) {
            setStats(await statsResponse.json())
          }
          if (profileResponse.ok) {
            setProfile(await profileResponse.json())
          }
        }
      })

    fetch(`${API}/api/players`)
      .then((response) => (response.ok ? response.json() : []))
      .then((payload) => setPlayers(payload))
      .catch(() => {})

    fetch(`${API}/api/lobby?web_user_id=${userId}`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setLobbies)
      .catch(() => {})
  }, [session?.user?.id])

  async function refreshAccount() {
    if (!me) {
      return
    }

    const response = await fetch(`${API}/api/web/me/${me.id}`)
    if (!response.ok) {
      return
    }

    const payload = await response.json()
    setMe(payload)

    if (payload.player_id) {
      const [statsResponse, profileResponse] = await Promise.all([
        fetch(`${API}/api/player/${payload.player_id}/stats`),
        fetch(`${API}/api/player/${payload.player_id}/full-profile`),
      ])

      if (statsResponse.ok) {
        setStats(await statsResponse.json())
      }
      if (profileResponse.ok) {
        setProfile(await profileResponse.json())
      }
    }
  }

  async function linkProfile() {
    if (!me || !linkId) {
      return
    }

    setLinking(true)
    setLinkMessage(null)

    const response = await fetch(`${API}/api/web/link-player`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: me.id, player_id: Number(linkId) }),
    })
    const payload = await response.json()

    if (response.ok) {
      setLinkMessage(`Профиль связан с ${payload.player_name}.`)
      await refreshAccount()
    } else {
      setLinkMessage(payload.detail ?? "Не удалось привязать профиль.")
    }

    setLinking(false)
  }

  async function askAssistant() {
    if (!question.trim() || !me?.player_id) {
      return
    }

    setAssistantLoading(true)
    setAssistantAnswer(null)

    try {
      const response = await fetch(`${API}/api/seasons/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_id: me.player_id, question: question.trim() }),
      })
      const payload = await response.json()
      setAssistantAnswer(payload.answer ?? "Ответ не был получен.")
    } catch {
      setAssistantAnswer("Ассистент сейчас недоступен.")
    } finally {
      setAssistantLoading(false)
    }
  }

  async function createLobby() {
    if (!newLobbyName.trim() || !me) {
      return
    }

    setCreatingLobby(true)
    try {
      const response = await fetch(`${API}/api/lobby`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newLobbyName.trim(), web_user_id: me.id }),
      })

      if (response.ok) {
        setNewLobbyName("")
        const nextLobbies = await fetch(`${API}/api/lobby?web_user_id=${me.id}`).then((nextResponse) =>
          nextResponse.ok ? nextResponse.json() : [],
        )
        setLobbies(nextLobbies)
      }
    } finally {
      setCreatingLobby(false)
    }
  }

  const activeSeason = useMemo(
    () => profile?.season_history.find((season) => season.status === "active") ?? profile?.season_history[0] ?? null,
    [profile?.season_history],
  )

  if (status === "loading" || !me) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка центра аккаунта...</div>
  }

  const avatar = me.player?.avatar_url ?? me.picture ?? null
  const displayName = me.player?.name ?? me.name

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="flex items-start gap-4">
            {avatar ? (
              <img src={avatar} alt="" className="h-16 w-16 rounded-full object-cover" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-accent/15 text-2xl font-semibold text-accent">
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <p className="eyebrow">Расширенный центр аккаунта</p>
                <h1 className="page-title">{displayName}</h1>
              </div>
              <p className="page-copy">
                Кабинет остается основным хабом участника. Эта страница работает как расширенный слой аккаунта для привязки
                профиля, создания лобби, доступа к ассистенту и входа в админские поверхности.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/workspace" className="ui-button-primary">
                  Открыть кабинет
                </Link>
                {me.player_id ? (
                  <Link href={`/players/${me.player_id}`} className="ui-button-secondary">
                    Публичный профиль
                  </Link>
                ) : null}
                <button onClick={() => signOut({ callbackUrl: "/" })} className="ui-button-tertiary">
                  Выйти
                </button>
              </div>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние аккаунта</p>
            <p className="mt-3 text-lg font-semibold text-text">{me.email ?? "Аккаунт сайта"}</p>
            <p className="mt-2 text-sm text-muted">
              {profile ? `Рейтинг ${profile.rating.rating} - уровень ${ratingTier(profile.rating.rating)}` : "Привяжите профиль лиги, чтобы открыть контекст прогресса."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {me.steam_id64 ? <span className="data-pill">Steam привязан</span> : null}
              {me.player?.telegram_id ? <span className="data-pill">Telegram привязан</span> : null}
              {me.is_system_admin ? <span className="data-pill">Системный админ</span> : null}
            </div>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Связанный игрок</p>
          <p className="stat-value">{me.player_id ? "Готово" : "Отсутствует"}</p>
          <p className="mt-2 text-sm text-muted">{me.player_id ? "История сезонов и телеметрия доступны" : "Сначала привяжите идентичность пилота"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Рейтинг</p>
          <p className="stat-value mono-data">{profile?.rating.rating ?? "--"}</p>
          <p className="mt-2 text-sm text-muted">{profile ? `Пик ${profile.rating.peak_rating}` : "Появится после привязки профиля"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Гонки</p>
          <p className="stat-value mono-data">{stats?.races ?? 0}</p>
          <p className="mt-2 text-sm text-muted">Зафиксировано гонок в карьере</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Активный сезон</p>
          <p className="stat-value">{activeSeason?.season_name ?? "Архив"}</p>
          <p className="mt-2 text-sm text-muted">
            {activeSeason ? `${activeSeason.position ? `P${activeSeason.position}` : "Позиция уточняется"} - ${activeSeason.points} очков` : "Нет контекста активного сезона"}
          </p>
        </div>
      </section>

      {!me.player_id ? (
        <section className="surface-panel p-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div>
              <p className="eyebrow">Привязать профиль игрока</p>
              <h2 className="mt-2 section-title">Свяжите веб-аккаунт с игровой идентичностью в лиге.</h2>
              <p className="mt-4 text-sm leading-7 text-muted">
                Это откроет историю сезонов, телеметрический анализ, контекст AI-инженера и вашу публичную страницу игрока.
              </p>
              <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                <select
                  value={linkId}
                  onChange={(event) => setLinkId(event.target.value)}
                  className="h-12 flex-1 rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                >
                  <option value="">Выберите профиль игрока</option>
                  {players.map((player) => (
                    <option key={player.id} value={player.id}>
                      #{player.id} - {player.name}
                    </option>
                  ))}
                </select>
                <button onClick={linkProfile} disabled={!linkId || linking} className="ui-button-primary">
                  {linking ? "Привязываем..." : "Привязать профиль"}
                </button>
              </div>
              {linkMessage ? <p className="mt-3 text-sm text-muted">{linkMessage}</p> : null}
            </div>

            <div className="surface-panel-muted p-5">
              <p className="eyebrow">Зачем это нужно</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
                <li>Публичная идентичность игрока становится каноничной для сезонов и гонок.</li>
                <li>Инструменты участника смогут корректно привязывать телеметрию и AI-анализ.</li>
                <li>Продуктовая оболочка остается дисциплинированной между объектами аккаунта и соревнования.</li>
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
        <div className="space-y-6">
          <div className="surface-panel overflow-hidden">
            <div className="border-b border-border px-6 py-5">
              <p className="eyebrow">Мои лобби</p>
              <h2 className="mt-2 section-title">Группы и членства, связанные с этим аккаунтом.</h2>
            </div>
            <div className="space-y-3 p-6">
              {lobbies.length > 0 ? (
                lobbies.map((lobby) => (
                  <Link key={lobby.id} href={`/lobby/${lobby.id}`} className="archive-row md:grid-cols-[minmax(0,1fr)_180px]">
                    <div>
                      <p className="text-lg font-semibold text-text">{lobby.name}</p>
                      <p className="mt-2 text-sm text-muted">
                        {lobby.members} участников - {lobby.seasons} сезонов
                      </p>
                    </div>
                    <div className="flex items-center justify-between gap-3 md:justify-end">
                      {lobby.your_role ? <span className="data-pill">{lobby.your_role}</span> : null}
                      <span className="text-sm text-info transition-colors hover:text-text">Открыть</span>
                    </div>
                  </Link>
                ))
              ) : (
                <div className="surface-panel-muted p-5">
                  <p className="text-sm text-muted">Вы еще не состоите ни в одном лобби. Войдите по инвайту или создайте новую группу.</p>
                </div>
              )}

              <div className="rounded-[16px] border border-border bg-surfaceAlt/60 p-4">
                <p className="text-sm font-medium text-text">Создать новое лобби</p>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                  <input
                    value={newLobbyName}
                    onChange={(event) => setNewLobbyName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        createLobby()
                      }
                    }}
                    placeholder="Название лобби"
                    className="h-12 flex-1 rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                  />
                  <button onClick={createLobby} disabled={creatingLobby || !newLobbyName.trim()} className="ui-button-primary">
                    {creatingLobby ? "Создаем..." : "Создать лобби"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {profile ? (
            <div className="surface-panel overflow-hidden">
              <div className="border-b border-border px-6 py-5">
                <p className="eyebrow">История сезонов</p>
                <h2 className="mt-2 section-title">Прогресс по чемпионатам.</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="data-table min-w-[720px]">
                  <thead>
                    <tr>
                      <th>Сезон</th>
                      <th>Статус</th>
                      <th className="text-right">Поз</th>
                      <th className="text-right">Очки</th>
                      <th className="text-right">Победы</th>
                      <th className="text-right">Подиумы</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.season_history.map((season) => (
                      <tr key={season.season_id}>
                        <td>
                          <Link href={`/season/${season.season_id}`} className="font-medium text-text transition-colors hover:text-accent">
                            {season.season_name}
                          </Link>
                          <p className="mt-1 text-xs text-muted">{season.team_name ?? "Команда не назначена"}</p>
                        </td>
                        <td className="text-sm text-muted">{season.status}</td>
                        <td className="text-right mono-data text-muted">{season.position ? `P${season.position}` : "--"}</td>
                        <td className="text-right mono-data font-semibold text-text">{season.points}</td>
                        <td className="text-right mono-data text-muted">{season.wins}</td>
                        <td className="text-right mono-data text-muted">{season.podiums}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {stats?.race_history?.length ? (
            <div className="surface-panel overflow-hidden">
              <div className="border-b border-border px-6 py-5">
                <p className="eyebrow">Недавняя история гонок</p>
                <h2 className="mt-2 section-title">Самые свежие классифицированные результаты.</h2>
              </div>
              <div className="space-y-3 p-6">
                {stats.race_history.slice(0, 6).map((race) => (
                  <Link key={race.race_id} href={`/race/${race.race_id}`} className="archive-row md:grid-cols-[110px_minmax(0,1fr)_160px]">
                    <div>
                      <p className="utility-kicker">Раунд</p>
                      <p className="mt-2 mono-data text-lg text-muted">{race.round ? `R${race.round}` : "--"}</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-text">{race.track_name ?? "Неизвестная трасса"}</p>
                      <p className="mt-2 text-sm text-muted">{race.team_name}</p>
                    </div>
                    <div className="flex items-center justify-between gap-3 md:justify-end">
                      <span className="data-pill">{race.position ? `P${race.position}` : "DNF"}</span>
                      <span className="mono-data text-sm text-text">{race.points} очк.</span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Срез карьеры</p>
            <div className="mt-4 space-y-3 text-sm leading-6 text-muted">
              <p>Победы: <span className="mono-data text-text">{stats?.wins ?? 0}</span></p>
              <p>Подиумы: <span className="mono-data text-text">{stats?.podiums ?? 0}</span></p>
              <p>DNFs: <span className="mono-data text-text">{stats?.dnfs ?? 0}</span></p>
              <p>Быстрейшие круги: <span className="mono-data text-text">{stats?.fastest_laps ?? 0}</span></p>
              <p>Лучший финиш: <span className="mono-data text-text">{stats?.best_finish ? `P${stats.best_finish}` : "--"}</span></p>
              <p>Средний финиш: <span className="mono-data text-text">{stats?.avg_position?.toFixed(1) ?? "--"}</span></p>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Ассистент</p>
            <p className="mt-3 text-sm leading-7 text-muted">
              Используйте облегченного ассистента участника для вопросов по аккаунту, когда не нужен полный поток сезонного инженера.
            </p>
            <div className="mt-4 space-y-3">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={4}
                placeholder="Спросите о прогрессе, текущей форме или о том, на чем сфокусироваться дальше..."
                className="w-full rounded-[12px] border border-border bg-[#0f141a] px-4 py-3 text-sm text-text outline-none transition-colors focus:border-borderStrong"
              />
              <button onClick={askAssistant} disabled={!me.player_id || !question.trim() || assistantLoading} className="ui-button-primary w-full">
                {assistantLoading ? "Анализируем..." : "Спросить ассистента"}
              </button>
              {assistantAnswer ? <div className="rounded-[12px] border border-border bg-surfaceAlt/70 p-4 text-sm leading-7 text-text">{assistantAnswer}</div> : null}
            </div>
          </div>

          {profile?.achievements?.length ? (
            <div className="surface-panel p-5">
              <p className="eyebrow">Достижения</p>
              <div className="mt-4 space-y-3">
                {profile.achievements.slice(0, 4).map((achievement) => (
                  <div key={achievement.code} className="rounded-[12px] border border-border bg-surfaceAlt/70 p-4">
                    <p className="font-medium text-text">{achievement.name}</p>
                    <p className="mt-2 text-sm text-muted">{achievement.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="surface-panel p-5">
            <p className="eyebrow">Следующие действия</p>
            <div className="mt-4 space-y-2">
              <Link href="/lobby/join" className="ui-button-secondary w-full">
                Вступить по инвайту
              </Link>
              <Link href="/practice" className="ui-button-tertiary w-full">
                История практики
              </Link>
              <Link href="/launcher" className="ui-button-tertiary w-full">
                Настройка лаунчера
              </Link>
              {me.is_system_admin ? (
                <Link href="/admin" className="ui-button-tertiary w-full">
                  Системная админка
                </Link>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
