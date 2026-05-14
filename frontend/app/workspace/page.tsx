"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface LobbyItem {
  id: number
  name: string
  members: number
  seasons: number
  your_role?: string
}

interface WorkspaceProfile {
  id: number
  name: string
  email: string | null
  picture: string | null
  player_id: number | null
  is_system_admin: boolean
  player?: {
    id: number
    name: string
    avatar_url: string | null
  }
}

interface ProfileSummary {
  season_history: {
    season_id: number
    season_name: string
    status: string
    position: number | null
    points: number
  }[]
  rating: {
    rating: number
    peak_rating: number
  }
}

export default function WorkspacePage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  const [profile, setProfile] = useState<WorkspaceProfile | null>(null)
  const [summary, setSummary] = useState<ProfileSummary | null>(null)
  const [lobbies, setLobbies] = useState<LobbyItem[]>([])

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login")
    }
  }, [router, status])

  useEffect(() => {
    if (!session?.user?.id) {
      return
    }

    const userId = session.user.id

    fetch(`${API}/api/web/me/${userId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(async (payload: WorkspaceProfile | null) => {
        setProfile(payload)

        if (payload?.player_id) {
          const response = await fetch(`${API}/api/player/${payload.player_id}/full-profile`)
          if (response.ok) {
            setSummary(await response.json())
          }
        }
      })
      .catch(() => {})

    fetch(`${API}/api/lobby?web_user_id=${userId}`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setLobbies)
      .catch(() => {})
  }, [session?.user?.id])

  if (status === "loading" || !profile) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка кабинета...</div>
  }

  const displayName = profile.player?.name ?? profile.name
  const avatar = profile.player?.avatar_url ?? profile.picture ?? null
  const activeSeason = summary?.season_history.find((season) => season.status === "active") ?? summary?.season_history[0] ?? null

  return (
    <div className="page-shell">
      <section className="surface-feature p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex items-start gap-4">
            {avatar ? (
              <img src={avatar} alt="" className="h-16 w-16 rounded-full object-cover" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-accent/20 text-2xl font-semibold text-accent">
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <p className="eyebrow">Кабинет участника</p>
                <h1 className="mt-2 font-display text-[2.8rem] leading-none tracking-[0.05em] text-text">{displayName}</h1>
              </div>
              <p className="max-w-[64ch] text-sm leading-7 text-muted">
                Здесь собраны ваши следующие действия, доступ к лобби, контекст прогресса и точки входа в операторский слой.
                Кабинет теперь явно отделен от публичной продуктовой оболочки.
              </p>
              <div className="flex flex-wrap gap-3">
                {activeSeason ? (
                  <Link href={`/season/${activeSeason.season_id}`} className="ui-button-primary">
                    Открыть текущий сезон
                  </Link>
                ) : (
                  <Link href="/seasons" className="ui-button-primary">
                    Открыть сезоны
                  </Link>
                )}
                {profile.player_id ? (
                  <Link href={`/players/${profile.player_id}`} className="ui-button-secondary">
                    Открыть публичный профиль
                  </Link>
                ) : (
                  <Link href="/me" className="ui-button-secondary">
                    Привязать профиль лиги
                  </Link>
                )}
                <Link href="/me" className="ui-button-tertiary">
                  Расширенные действия с аккаунтом
                </Link>
              </div>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние аккаунта</p>
            <p className="mt-3 text-lg font-semibold text-text">{profile.email ?? "Аккаунт сайта"}</p>
            <p className="mt-2 text-sm text-muted">
              {summary ? `Рейтинг ${summary.rating.rating} · Пик ${summary.rating.peak_rating}` : "Привяжите профиль лиги, чтобы видеть прогресс и телеметрический контекст."}
            </p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Связанный профиль</p>
          <p className="stat-value">{profile.player_id ? "Да" : "Нет"}</p>
          <p className="mt-2 text-sm text-muted">{profile.player_id ? "Готов к истории сезонов и телеметрии" : "Используйте центр аккаунта, чтобы привязать профиль пилота"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Мои лобби</p>
          <p className="stat-value mono-data">{lobbies.length}</p>
          <p className="mt-2 text-sm text-muted">Группы, где вы состоите</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Текущий сезон</p>
          <p className="stat-value">{activeSeason?.season_name ?? "Архив"}</p>
          <p className="mt-2 text-sm text-muted">
            {activeSeason ? `${activeSeason.position ? `P${activeSeason.position}` : "Позиция уточняется"} · ${activeSeason.points} очков` : "Вступите или привяжите сезон, чтобы видеть прогресс"}
          </p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Операторский доступ</p>
          <p className="stat-value">{profile.is_system_admin ? "Включен" : "Участник"}</p>
          <p className="mt-2 text-sm text-muted">{profile.is_system_admin ? "Доступны системные админ-инструменты" : "Инструменты оператора сезона появляются только при необходимости"}</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_340px]">
        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Мои лобби</p>
            <h2 className="mt-2 section-title">Группы лиги и активные членства.</h2>
          </div>
          <div className="space-y-3 p-6">
            {lobbies.length > 0 ? (
              lobbies.map((lobby) => (
                <Link key={lobby.id} href={`/lobby/${lobby.id}`} className="archive-row md:grid-cols-[minmax(0,1fr)_160px]">
                  <div>
                    <p className="text-lg font-semibold text-text">{lobby.name}</p>
                    <p className="mt-2 text-sm text-muted">
                      {lobby.members} участников · {lobby.seasons} сезонов
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
                <p className="text-sm text-muted">Вы еще не состоите ни в одном лобби. Войдите по инвайту, чтобы попасть в активную группу лиги.</p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Следующие действия</p>
            <div className="mt-4 space-y-2">
              <Link href="/lobby/join" className="ui-button-secondary w-full">
                Вступить по инвайту
              </Link>
              <Link href="/practice" className="ui-button-tertiary w-full">
                Инструменты практики
              </Link>
              <Link href="/launcher" className="ui-button-tertiary w-full">
                Настройка лаунчера
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Операторский слой</p>
            <p className="mt-3 text-sm leading-7 text-muted">
              Операторские действия вынесены из публичной оболочки. Используйте системную админку или вкладки управления
              сезоном только когда у вас есть явная модераторская зона ответственности.
            </p>
            <div className="mt-4 space-y-2">
              {profile.is_system_admin ? (
                <Link href="/admin" className="ui-button-secondary w-full">
                  Открыть системную админку
                </Link>
              ) : null}
              {/* "Открыть управление сезоном" button hidden — see PR 1.2.5; manage page is stubbed. */}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
