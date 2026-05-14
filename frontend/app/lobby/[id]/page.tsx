"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { useEffect, useState } from "react"
import type { LobbyInfo, LobbyMember } from "@/lib/api"
import { apiFetch } from "@/lib/api-client"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export default function LobbyPage() {
  const { id } = useParams<{ id: string }>()
  const { data: session } = useSession()
  const userId = session?.user?.id ? Number(session.user.id) : undefined

  const [lobby, setLobby] = useState<LobbyInfo | null>(null)
  const [members, setMembers] = useState<LobbyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [newSeasonName, setNewSeasonName] = useState("")
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!id) {
      return
    }

    Promise.all([
      apiFetch(`/api/lobby/${id}${userId ? `?web_user_id=${userId}` : ""}`).then((response) => (response.ok ? response.json() : null)),
      apiFetch(`/api/lobby/${id}/members`).then((response) => (response.ok ? response.json() : [])),
    ])
      .then(([nextLobby, nextMembers]) => {
        setLobby(nextLobby)
        setMembers(nextMembers)
      })
      .finally(() => setLoading(false))
  }, [id, userId])

  async function handleCreateSeason() {
    if (!newSeasonName.trim() || !userId) {
      return
    }

    setCreating(true)
    try {
      const response = await apiFetch(`/api/lobby/${id}/seasons`, {
        method: "POST",
        body: JSON.stringify({ requester_id: userId, name: newSeasonName.trim() }),
      })

      if (response.ok) {
        setNewSeasonName("")
        const refreshedLobby = await apiFetch(`/api/lobby/${id}?web_user_id=${userId}`).then((nextResponse) =>
          nextResponse.ok ? nextResponse.json() : null,
        )
        setLobby(refreshedLobby)
      }
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка группового кабинета...</div>
  }

  if (!lobby) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Групповой кабинет не найден.</div>
  }

  const canOperate = lobby.your_role === "admin" || lobby.your_role === "moderator"
  const activeSeason = lobby.seasons.find((season) => season.status === "active") ?? lobby.seasons[0] ?? null
  const archive = activeSeason ? lobby.seasons.filter((season) => season.id !== activeSeason.id) : []
  const inviteLink = typeof window !== "undefined" && lobby.invite_code ? `${window.location.origin}/lobby/join?code=${lobby.invite_code}` : ""

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Групповой кабинет</p>
            <h1 className="page-title">{lobby.name}</h1>
            <p className="page-copy">
              Лобби это групповой объект системы. Оно владеет участниками, инвайт-потоком и стеком сезонов, но сам сезон
              остается основной соревновательной поверхностью.
            </p>
            <div className="flex flex-wrap gap-3">
              {activeSeason ? (
                <Link href={`/season/${activeSeason.id}`} className="ui-button-primary">
                  Открыть активный сезон
                </Link>
              ) : null}
              <Link href="/workspace" className="ui-button-secondary">
                Назад в кабинет
              </Link>
              {canOperate ? (
                <Link href="/lobby/join" className="ui-button-tertiary">
                  Вход по инвайту
                </Link>
              ) : null}
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние группы</p>
            <p className="mt-3 text-2xl font-semibold text-text">{lobby.your_role}</p>
            <p className="mt-2 text-sm text-muted">
              {lobby.members_count} участников - {lobby.seasons.length} сезонов
            </p>
            <p className="mt-4 text-xs text-muted">Владелец: {lobby.creator_name ?? "Неизвестно"}</p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Участники</p>
          <p className="stat-value mono-data">{lobby.members_count}</p>
          <p className="mt-2 text-sm text-muted">Аккаунтов в этой группе</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Сезоны</p>
          <p className="stat-value mono-data">{lobby.seasons.length}</p>
          <p className="mt-2 text-sm text-muted">Чемпионатов в этой группе</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Основной сезон</p>
          <p className="stat-value">{activeSeason?.name ?? "Нет"}</p>
          <p className="mt-2 text-sm text-muted">
            {activeSeason ? `${activeSeason.races_played}/${activeSeason.total_rounds} этапов завершено` : "Создайте сезон, чтобы запустить соревновательный слой"}
          </p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Состояние инвайта</p>
          <p className="stat-value">{lobby.invite_code ? "Готов" : "Закрыт"}</p>
          <p className="mt-2 text-sm text-muted">{lobby.invite_code ? "Участники могут войти по коду" : "Код приглашения недоступен"}</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_320px]">
        <div className="space-y-6">
          {activeSeason ? (
            <section className="surface-panel overflow-hidden">
              <div className="border-b border-border px-6 py-5">
                <p className="eyebrow">Активный сезон</p>
                <h2 className="mt-2 section-title">Группа выходит в соревнование через свой текущий чемпионат.</h2>
              </div>
              <div className="p-6">
                <Link href={`/season/${activeSeason.id}`} className="archive-row">
                  <div>
                    <p className="utility-kicker">Текущий</p>
                    <p className="mt-2 mono-data text-lg text-muted">S{activeSeason.id}</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-text">{activeSeason.name}</p>
                    <p className="mt-2 text-sm text-muted">
                      {activeSeason.races_played}/{activeSeason.total_rounds} этапов завершено. Используйте оболочку сезона для
              таблицы, календаря, оперативного состояния и истории гонок.
                    </p>
                  </div>
                  <div className="flex items-center justify-between gap-3 md:justify-end">
                    <span className="data-pill">{activeSeason.status}</span>
                    <span className="text-sm text-info transition-colors hover:text-text">Открыть сезон</span>
                  </div>
                </Link>
              </div>
            </section>
          ) : (
            <section className="surface-panel p-8 text-center sm:p-10">
              <p className="eyebrow">Сезона пока нет</p>
              <h2 className="mt-3 section-title">Для этой группы еще не настроен чемпионат.</h2>
              <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
                Создайте первый сезон, чтобы превратить эту группу из контейнера участников в живую историю чемпионата.
              </p>
            </section>
          )}

          <section className="surface-panel overflow-hidden">
            <div className="border-b border-border px-6 py-5">
              <p className="eyebrow">Архив сезонов</p>
              <h2 className="mt-2 section-title">Все чемпионаты этой группы.</h2>
            </div>
            <div className="space-y-3 p-6">
              {archive.length > 0 ? (
                archive.map((season) => (
                  <Link key={season.id} href={`/season/${season.id}`} className="archive-row md:grid-cols-[110px_minmax(0,1fr)_160px]">
                    <div>
                      <p className="utility-kicker">Сезон</p>
                      <p className="mt-2 mono-data text-lg text-muted">S{season.id}</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-text">{season.name}</p>
                      <p className="mt-2 text-sm text-muted">{season.races_played}/{season.total_rounds} этапов завершено</p>
                    </div>
                    <div className="flex items-center justify-between gap-3 md:justify-end">
                      <span className="data-pill">{season.status}</span>
                      <span className="text-sm text-info transition-colors hover:text-text">Открыть</span>
                    </div>
                  </Link>
                ))
              ) : (
                <div className="surface-panel-muted p-5">
                  <p className="text-sm text-muted">Кроме текущего чемпионата, исторических сезонов пока нет.</p>
                </div>
              )}
            </div>
          </section>

          {canOperate ? (
            <section className="surface-panel p-6">
              <p className="eyebrow">Создать сезон</p>
              <h2 className="mt-2 section-title">Запустите новый чемпионат внутри этой группы.</h2>
              <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                <input
                  value={newSeasonName}
                  onChange={(event) => setNewSeasonName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleCreateSeason()
                    }
                  }}
                  placeholder="Название сезона"
                  className="h-12 flex-1 rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                />
                <button onClick={handleCreateSeason} disabled={creating || !newSeasonName.trim()} className="ui-button-primary">
                  {creating ? "Создаем..." : "Создать сезон"}
                </button>
              </div>
            </section>
          ) : null}
        </div>

        <div className="space-y-4">
          <section className="surface-panel p-5">
            <p className="eyebrow">Участники</p>
            <div className="mt-4 space-y-3">
              {members.map((member) => (
                <div key={member.web_user_id} className="flex items-center gap-3">
                  {member.picture ? (
                    <img src={member.picture} alt="" className="h-9 w-9 rounded-full object-cover" />
                  ) : (
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/15 text-sm font-semibold text-accent">
                      {member.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">{member.name}</p>
                    <p className="text-xs text-muted">{member.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {canOperate && lobby.invite_code ? (
            <section className="surface-panel p-5">
              <p className="eyebrow">Инвайт</p>
              <div className="mt-4 space-y-3">
                <div className="rounded-[12px] border border-border bg-surfaceAlt/70 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-dim">Код</p>
                  <p className="mt-2 mono-data text-lg text-text">{lobby.invite_code}</p>
                  <button onClick={() => navigator.clipboard.writeText(lobby.invite_code ?? "")} className="mt-3 ui-button-tertiary">
                    Скопировать код
                  </button>
                </div>
                <div className="rounded-[12px] border border-border bg-surfaceAlt/70 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-dim">Ссылка входа</p>
                  <p className="mt-2 break-all text-sm text-muted">{inviteLink}</p>
                  <button onClick={() => navigator.clipboard.writeText(inviteLink)} className="mt-3 ui-button-tertiary">
                    Скопировать ссылку
                  </button>
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </section>
    </div>
  )
}
