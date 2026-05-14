import Link from "next/link"
import { notFound } from "next/navigation"
import { Breadcrumbs } from "@/components/Breadcrumbs"
import { api } from "@/lib/api"
import { formatDate } from "@/lib/utils"

export const revalidate = 60

function ratingRank(rating: number) {
  if (rating >= 2000) return "Грандмастер"
  if (rating >= 1800) return "Мастер"
  if (rating >= 1600) return "Алмаз"
  if (rating >= 1400) return "Золото"
  if (rating >= 1200) return "Серебро"
  return "Бронза"
}

export default async function PlayerProfilePage({ params }: { params: { id: string } }) {
  const playerId = Number(params.id)
  const [profile, trendsData, ratingHistory] = await Promise.all([
    api.fullProfile(playerId).catch(() => null),
    api.trends(playerId).catch(() => null),
    api.ratingHistory(playerId).catch(() => []),
  ])

  if (!profile) {
    notFound()
  }

  const trends = trendsData?.trends ?? []
  const activeSeason = profile.season_history.find((season) => season.status === "active") ?? profile.season_history[0] ?? null
  const recentRaces = trends.slice(-6).reverse()
  const latestRating = ratingHistory[ratingHistory.length - 1]?.rating_after ?? profile.rating.rating
  const bestRating = ratingHistory.reduce((best, entry) => Math.max(best, entry.rating_after), profile.rating.peak_rating)
  const introLine = activeSeason
    ? `${activeSeason.season_name}: ${activeSeason.position ? `P${activeSeason.position}` : "вне классификации"} с ${activeSeason.points} очками${activeSeason.team_name ? ` за ${activeSeason.team_name}` : ""}.`
    : "Профиль игрока с историей гонок, динамикой рейтинга и результатами по сезонам."

  return (
    <div className="page-stack">
      <Breadcrumbs items={[{ href: "/", label: "Главная" }, { href: "/players", label: "Игроки" }, { label: profile.name }]} />

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
          <div className="flex items-start gap-4">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="" className="h-20 w-20 rounded-full object-cover" />
            ) : (
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-accent/20 text-3xl font-semibold text-accent">
                {profile.name.charAt(0).toUpperCase()}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <p className="eyebrow">Профиль игрока</p>
                <h1 className="mt-2 font-display text-[3rem] leading-none tracking-[0.04em] text-text">{profile.name}</h1>
              </div>
              <p className="max-w-[60ch] text-sm leading-7 text-muted">{introLine}</p>
              <div className="flex flex-wrap gap-2">
                <span className="state-chip">{ratingRank(profile.rating.rating)}</span>
                {profile.current_team ? <span className="data-pill">{profile.current_team}</span> : null}
                {profile.current_driver ? <span className="data-pill">{profile.current_driver}</span> : null}
                {profile.created_at ? <span className="data-pill">В лиге с {formatDate(profile.created_at)}</span> : null}
              </div>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Текущий рейтинг</p>
            <p className="mt-3 mono-data text-4xl font-semibold text-text">{latestRating}</p>
            <p className="mt-2 text-sm text-muted">Пик {bestRating}</p>
            <p className="mt-4 text-sm text-muted">{profile.rating.races_rated} рейтинговых гонок в истории.</p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Гонок в карьере</p>
          <p className="stat-value mono-data">{profile.stats.races}</p>
          <p className="mt-2 text-sm text-muted">Зафиксированные старты в лиге</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Победы</p>
          <p className="stat-value mono-data">{profile.stats.wins}</p>
          <p className="mt-2 text-sm text-muted">{profile.stats.win_rate}% винрейт</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Подиумы</p>
          <p className="stat-value mono-data">{profile.stats.podiums}</p>
          <p className="mt-2 text-sm text-muted">{profile.stats.podium_rate}% подиумов</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Средний финиш</p>
          <p className="stat-value mono-data">{profile.stats.avg_position ? profile.stats.avg_position.toFixed(1) : "--"}</p>
          <p className="mt-2 text-sm text-muted">Лучший финиш {profile.stats.best_finish ? `P${profile.stats.best_finish}` : "--"}</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_340px]">
        <div className="list-panel">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Последние гонки</p>
            <h2 className="mt-2 section-title">Свежие опубликованные результаты этого игрока.</h2>
          </div>
          {recentRaces.length > 0 ? (
            recentRaces.map((race) => (
              <div key={race.race_id} className="list-row md:grid-cols-[96px_minmax(0,1fr)_180px] md:items-center">
                <div>
                  <p className="utility-kicker">Раунд</p>
                  <p className="mt-2 mono-data text-lg text-muted">{race.round ? `R${race.round}` : "--"}</p>
                </div>
                <div>
                  <Link href={`/race/${race.race_id}`} className="text-lg font-semibold text-text transition-colors hover:text-accent">
                    {race.track ?? "Неизвестная трасса"}
                  </Link>
                  <p className="mt-1 text-sm text-muted">
                    {race.position ? `Финиш P${race.position}` : "Нет классифицированного финиша"}
                    {typeof race.grid_delta === "number" ? ` | Изменение от грида ${race.grid_delta > 0 ? "+" : ""}${race.grid_delta}` : ""}
                  </p>
                </div>
                <div className="text-sm md:text-right">
                  <p className="mono-data text-lg font-semibold text-text">{race.points} очк.</p>
                  <p className="text-muted">{race.has_fastest_lap ? "Быстрейший круг" : "Опубликованный результат"}</p>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-6 text-sm text-muted">Для этого профиля пока нет недавних гонок.</div>
          )}
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Текущий сезон</p>
            {activeSeason ? (
              <div className="mt-4 space-y-3">
                <div>
                  <p className="text-lg font-semibold text-text">{activeSeason.season_name}</p>
                  <p className="mt-1 text-sm text-muted">
                    {activeSeason.position ? `P${activeSeason.position}` : "Вне классификации"} | {activeSeason.points} очков
                  </p>
                  {activeSeason.team_name ? <p className="mt-1 text-sm text-muted">{activeSeason.team_name}</p> : null}
                </div>
                <Link href={`/season/${activeSeason.season_id}`} className="ui-button-secondary w-full">
                  Открыть сезон
                </Link>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted">Для этого игрока пока нет записи в текущем сезоне.</p>
            )}
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Маркеры карьеры</p>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                <span className="text-sm text-muted">Быстрейшие круги</span>
                <span className="mono-data font-semibold text-text">{profile.stats.fastest_laps}</span>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                <span className="text-sm text-muted">DNFs</span>
                <span className="mono-data font-semibold text-text">{profile.stats.dnfs}</span>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                <span className="text-sm text-muted">Лучший прорыв</span>
                <span className="mono-data font-semibold text-text">
                  {typeof profile.stats.best_recovery === "number" ? `${profile.stats.best_recovery > 0 ? "+" : ""}${profile.stats.best_recovery}` : "--"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted">Достижения</span>
                <span className="mono-data font-semibold text-text">{profile.achievements.length}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">История сезонов</p>
          <h2 className="mt-2 section-title">Прогресс по чемпионатам.</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[780px]">
            <thead>
              <tr>
                <th>Сезон</th>
                <th className="text-right">Поз</th>
                <th className="text-right">Очки</th>
                <th className="text-right">Победы</th>
                <th className="text-right">Подиумы</th>
                <th className="text-right">DNFs</th>
                <th className="text-right">Открыть</th>
              </tr>
            </thead>
            <tbody>
              {profile.season_history.map((season) => (
                <tr key={season.season_id}>
                  <td>
                    <div className="font-medium text-text">{season.season_name}</div>
                    <div className="text-xs text-muted">{season.status}</div>
                  </td>
                  <td className="text-right mono-data text-text">{season.position ? `P${season.position}` : "--"}</td>
                  <td className="text-right mono-data text-text">{season.points}</td>
                  <td className="text-right mono-data text-muted">{season.wins}</td>
                  <td className="text-right mono-data text-muted">{season.podiums}</td>
                  <td className="text-right mono-data text-muted">{season.dnfs}</td>
                  <td className="text-right">
                    <Link href={`/season/${season.season_id}`} className="text-sm text-info transition-colors hover:text-text">
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="surface-panel p-6">
        <p className="eyebrow">Достижения</p>
        <h2 className="mt-2 section-title">Открытые карьерные метки.</h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {profile.achievements.length > 0 ? (
            profile.achievements.map((achievement) => (
              <div key={achievement.code} className="surface-panel-muted p-4">
                <p className="text-base font-semibold text-text">{achievement.name}</p>
                <p className="mt-2 text-sm leading-7 text-muted">{achievement.description}</p>
              </div>
            ))
          ) : (
            <div className="surface-panel-muted p-4">
              <p className="text-sm text-muted">Достижения пока не открыты.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
