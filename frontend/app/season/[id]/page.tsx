import Link from "next/link"
import { notFound } from "next/navigation"
import { PlayerBadge } from "@/components/PlayerBadge"
import { PointsBar } from "@/components/PointsBar"
import { SeasonNav } from "@/components/SeasonNav"
import { TeamColorBar } from "@/components/TeamColorBar"
import { getSeasonOverviewBundle } from "@/lib/site-data"
import { formatDate, formatLapTime } from "@/lib/utils"

export const revalidate = 30

export default async function SeasonOverviewPage({ params }: { params: { id: string } }) {
  const seasonId = Number(params.id)
  const { season, standings, constructors, calendar, races, records } = await getSeasonOverviewBundle(seasonId)

  if (!season) {
    notFound()
  }

  const humanStandings = standings.filter((entry) => entry.is_human)
  const visibleDrivers = humanStandings.length > 0 ? humanStandings : standings
  const completedRounds = calendar.filter((entry) => entry.completed).length
  const nextRace = calendar.find((entry) => !entry.completed) ?? null
  const latestRace = [...races].sort((a, b) => b.round - a.round)[0] ?? null
  const leader = visibleDrivers[0] ?? null
  const chaser = visibleDrivers[1] ?? null
  const constructorLeader = constructors[0] ?? null
  const maxPoints = visibleDrivers[0]?.total_points ?? 1
  const recordHeadlines = records.slice(0, 3)
  const progressTotal = calendar.length || season.total_rounds

  return (
    <div className="page-stack">
      <SeasonNav seasonId={season.id} seasonName={season.name} status={season.status} lobbyId={season.lobby_id} />

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.12fr)_320px] lg:items-start">
          <div className="space-y-4">
            <p className="eyebrow">{season.status === "active" ? "Текущий сезон" : "Сводка сезона"}</p>
            <h2 className="section-title">
              {leader && chaser
                ? `${leader.driver_name} лидирует с отрывом в ${leader.total_points - chaser.total_points} очков.`
                : "Таблица, календарь и последняя сводка гонки собраны в одном сезонном экране."}
            </h2>
            <p className="page-copy">
              {nextRace
                ? `${completedRounds} из ${progressTotal} этапов уже опубликованы. Следующим по календарю идет ${nextRace.track_name}.`
                : `Все ${progressTotal} этапов завершены. Используйте эту страницу, чтобы разобрать итоговую таблицу, последнюю гонку и рекорды сезона.`}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/season/${seasonId}/standings`} className="ui-button-primary">
                Таблица
              </Link>
              <Link href={`/season/${seasonId}/calendar`} className="ui-button-secondary">
                Календарь
              </Link>
              <Link href={`/season/${seasonId}/live`} className="ui-button-tertiary">
                Live
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние сезона</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-lg font-semibold text-text">{completedRounds}/{progressTotal} этапов завершено</p>
                <p className="mt-1 text-sm text-muted">{season.status === "active" ? "Активный чемпионат" : "Архивный чемпионат"}</p>
              </div>
              <div>
                <p className="utility-kicker">Следующий этап</p>
                <p className="mt-2 text-base font-semibold text-text">{nextRace?.track_name ?? "Следующих этапов нет"}</p>
                <p className="mt-1 text-sm text-muted">{nextRace ? `Раунд ${nextRace.round}` : "Сезон завершен"}</p>
              </div>
              <div>
                <p className="utility-kicker">Последний отчет</p>
                <p className="mt-2 text-base font-semibold text-text">{latestRace?.track_name ?? "Гонок еще нет"}</p>
                <p className="mt-1 text-sm text-muted">{latestRace ? formatDate(latestRace.raced_at) : "Появится после первой загрузки"}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Лидер чемпионата</p>
          <p className="stat-value">{leader?.driver_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">{leader ? `${leader.total_points} очков` : "Ждем первую гонку"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Отрыв от P2</p>
          <p className="stat-value mono-data">{leader && chaser ? leader.total_points - chaser.total_points : "--"}</p>
          <p className="mt-2 text-sm text-muted">{chaser ? `до ${chaser.driver_name}` : "Преследователя пока нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Этапов завершено</p>
          <p className="stat-value mono-data">
            {completedRounds}/{progressTotal}
          </p>
          <p className="mt-2 text-sm text-muted">Прогресс сезона</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Лидер конструкторов</p>
          <p className="stat-value">{constructorLeader?.team_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">
            {constructorLeader ? `${constructorLeader.total_points} командных очков` : "Таблица еще не заполнена"}
          </p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.16fr)_360px]">
        <div className="surface-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-6 py-5">
            <div>
              <p className="eyebrow">Таблица чемпионата</p>
              <h2 className="mt-2 section-title">Порядок пилотов с первого взгляда.</h2>
            </div>
            <Link href={`/season/${seasonId}/standings`} className="ui-button-tertiary">
              Полная таблица
            </Link>
          </div>
          <div className="overflow-x-auto p-6">
            <table className="data-table min-w-[760px]">
              <thead>
                <tr>
                  <th>Поз</th>
                  <th>Пилот</th>
                  <th className="text-right">Победы</th>
                  <th className="text-right">FL</th>
                  <th className="text-right">Очки</th>
                </tr>
              </thead>
              <tbody>
                {visibleDrivers.slice(0, 8).map((entry) => (
                  <tr key={entry.driver_id}>
                    <td className="mono-data text-muted">P{entry.position}</td>
                    <td>
                      <div className="flex items-center gap-3">
                        <TeamColorBar color={entry.team_color} className="h-8" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            {entry.player_id ? (
                              <Link href={`/players/${entry.player_id}`} className="font-medium text-text transition-colors hover:text-accent">
                                {entry.driver_name}
                              </Link>
                            ) : (
                              <span className="font-medium text-text">{entry.driver_name}</span>
                            )}
                            {entry.is_human ? <PlayerBadge /> : null}
                          </div>
                          <div className="text-xs text-muted">{entry.team_name}</div>
                          <div className="mt-2">
                            <PointsBar points={entry.total_points} maxPoints={maxPoints} color={entry.team_color} />
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="text-right mono-data text-muted">{entry.wins}</td>
                    <td className="text-right mono-data text-muted">{entry.fastest_laps}</td>
                    <td className="text-right mono-data font-semibold text-text">{entry.total_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Следующий этап</p>
            <h3 className="mt-3 text-xl font-semibold text-text">{nextRace?.track_name ?? "Сезон завершен"}</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              {nextRace
                ? `Раунд ${nextRace.round} станет следующим изменением состояния для этого сезона.`
                : "В этом чемпионате больше не осталось запланированных этапов."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href={`/season/${seasonId}/calendar`} className="ui-button-tertiary">
                Календарь
              </Link>
              <Link href={`/season/${seasonId}/live`} className="ui-button-tertiary">
                Live
              </Link>
              <Link href={`/season/${seasonId}/engineer`} className="ui-button-tertiary">
                Инженер
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Последняя опубликованная гонка</p>
            <h3 className="mt-3 text-xl font-semibold text-text">{latestRace?.track_name ?? "Гонок пока не зафиксировано"}</h3>
            <p className="mt-2 text-sm text-muted">{latestRace ? formatDate(latestRace.raced_at) : "Сводки гонок появятся здесь после первой загрузки."}</p>
            {latestRace ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Link href={`/race/${latestRace.id}`} className="ui-button-secondary h-10 px-4">
                  Сводка гонки
                </Link>
                <Link href={`/race/${latestRace.id}/analysis`} className="ui-button-tertiary">
                  Анализ
                </Link>
              </div>
            ) : null}
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Рекорды трасс</p>
            <div className="mt-4 space-y-4">
              {recordHeadlines.length > 0 ? (
                recordHeadlines.map((record) => (
                  <div key={record.track_id} className="border-b border-border pb-4 last:border-b-0 last:pb-0">
                    <p className="text-sm font-semibold text-text">{record.track_name}</p>
                    <p className="mt-2 mono-data text-lg text-text">{formatLapTime(record.best_lap_ms)}</p>
                    <p className="mt-1 text-xs text-muted">{record.driver_name}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted">Рекорды трасс появятся здесь по мере публикации гонок.</p>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="list-panel">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Календарь</p>
            <h2 className="mt-2 section-title">Предстоящие и завершенные этапы по порядку.</h2>
          </div>
          {calendar.slice(0, 6).map((entry) => (
            <div key={entry.round} className="list-row md:grid-cols-[96px_minmax(0,1fr)_180px] md:items-center">
              <div>
                <p className="utility-kicker">Раунд</p>
                <p className="mt-2 mono-data text-lg text-muted">R{entry.round}</p>
              </div>
              <div>
                <p className="text-lg font-semibold text-text">{entry.track_name}</p>
                <p className="mt-1 text-sm text-muted">
                  {entry.completed ? "Опубликован в архиве гонок." : "Ожидает загрузки."}
                </p>
              </div>
              <div className="flex items-center justify-between gap-3 md:justify-end">
                <span className="data-pill">{entry.completed ? "Завершен" : "Скоро"}</span>
                {entry.race_id ? (
                  <Link href={`/race/${entry.race_id}`} className="text-sm text-info transition-colors hover:text-text">
                    Сводка гонки
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Конструкторы</p>
            <h2 className="mt-2 section-title">Командная таблица как вторичный срез.</h2>
          </div>
          <div className="overflow-x-auto p-6">
            <table className="data-table min-w-[640px]">
              <thead>
                <tr>
                  <th>Поз</th>
                  <th>Команда</th>
                  <th className="text-right">Победы</th>
                  <th className="text-right">Очки</th>
                </tr>
              </thead>
              <tbody>
                {constructors.slice(0, 8).map((team) => (
                  <tr key={team.team_id}>
                    <td className="mono-data text-muted">P{team.position}</td>
                    <td>
                      <div className="flex items-center gap-3">
                        <TeamColorBar color={team.team_color} className="h-8" />
                        <div>
                          <div className="font-medium text-text">{team.team_name}</div>
                          <div className="text-xs text-muted">{[team.driver_1, team.driver_2].filter(Boolean).join(" / ") || "Состав ожидается"}</div>
                        </div>
                      </div>
                    </td>
                    <td className="text-right mono-data text-muted">{team.wins}</td>
                    <td className="text-right mono-data font-semibold text-text">{team.total_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
