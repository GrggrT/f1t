import Link from "next/link"
import { api } from "@/lib/api"
import { PageIntro } from "@/components/PageIntro"
import { TeamColorBar } from "@/components/TeamColorBar"
import { PlayerBadge } from "@/components/PlayerBadge"
import { PointsBar } from "@/components/PointsBar"

export const dynamic = "force-dynamic"

export default async function SeasonStandingsPage({ params }: { params: { id: string } }) {
  const seasonId = Number(params.id)

  const [driverStandings, constructors] = await Promise.all([
    api.standings(seasonId).catch(() => []),
    api.constructors(seasonId).catch(() => []),
  ])

  const championshipGrid = driverStandings.filter((entry) => entry.is_human)
  const visibleDrivers = championshipGrid.length > 0 ? championshipGrid : driverStandings
  const leader = visibleDrivers[0] ?? null
  const chaser = visibleDrivers[1] ?? null
  const maxDriverPoints = visibleDrivers[0]?.total_points ?? 1
  const maxConstructorPoints = constructors[0]?.total_points ?? 1

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Таблица сезона"
        title="Порядок чемпионата, с контекстом до таблицы."
        description={
          <>
            Страница таблицы теперь открывается живой картиной чемпионата, а уже потом переходит к полной таблице пилотов и
            конструкторов. Она рассчитана на повторные заходы и быстрое чтение, а не на холодный dump таблиц.
          </>
        }
        actions={
          <>
            <Link href={`/season/${seasonId}`} className="ui-button-secondary">
              Обзор сезона
            </Link>
            <Link href={`/season/${seasonId}/calendar`} className="ui-button-tertiary">
              Календарь
            </Link>
          </>
        }
        meta={
          <>
            <span className="data-pill">{visibleDrivers.length} пилотов в таблице</span>
            <span className="data-pill">{constructors.length} конструкторов</span>
          </>
        }
      />

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Лидер</p>
          <p className="stat-value">{leader?.driver_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">{leader ? `${leader.total_points} очков` : "Ждем первый результат"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Отрыв от P2</p>
          <p className="stat-value mono-data">{leader && chaser ? leader.total_points - chaser.total_points : 0}</p>
          <p className="mt-2 text-sm text-muted">{chaser ? `над ${chaser.driver_name}` : "Преследователя пока нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Больше всего побед</p>
          <p className="stat-value mono-data">{Math.max(...visibleDrivers.map((entry) => entry.wins), 0)}</p>
          <p className="mt-2 text-sm text-muted">Победы гонок у лидирующей группы</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Лидер конструкторов</p>
          <p className="stat-value">{constructors[0]?.team_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">
            {constructors[0] ? `${constructors[0].total_points} командных очков` : "Таблица конструкторов еще не заполнена"}
          </p>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border px-6 py-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Чемпионат пилотов</p>
            <h2 className="mt-2 section-title">Пилоты лиги, отсортированные по результату сезона.</h2>
          </div>
          <p className="max-w-[54ch] text-sm leading-6 text-muted">
            Когда на гриде смешаны участники и AI-слоты, приоритет отдается людям. Командные маркеры и шкалы очков
            помогают считывать таблицу с первого взгляда.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[760px]">
            <thead>
              <tr>
                <th>Поз</th>
                <th>Пилот</th>
                <th className="text-right">Победы</th>
                <th className="text-right">Подиумы</th>
                <th className="text-right">FL</th>
                <th className="text-right">DNF</th>
                <th className="text-right">Очки</th>
              </tr>
            </thead>
            <tbody>
              {visibleDrivers.map((entry) => (
                <tr key={entry.driver_id} className={entry.is_human ? "player-row" : undefined}>
                  <td className="mono-data text-muted">P{entry.position}</td>
                  <td>
                    <div className="flex items-center gap-3">
                      <TeamColorBar color={entry.team_color} className="h-10" />
                      <div className="min-w-0 flex-1">
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
                        <p className="mt-1 text-xs text-muted">{entry.team_name}</p>
                        <div className="mt-3">
                          <PointsBar points={entry.total_points} maxPoints={maxDriverPoints} color={entry.team_color} />
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="text-right mono-data text-muted">{entry.wins}</td>
                  <td className="text-right mono-data text-muted">{entry.podiums}</td>
                  <td className="text-right mono-data text-muted">{entry.fastest_laps}</td>
                  <td className="text-right mono-data text-muted">{entry.dnfs}</td>
                  <td className="text-right mono-data font-semibold text-text">{entry.total_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border px-6 py-4">
          <p className="insight-line">
            Таблица остается плотной, но больше не стартует холодно. Главная борьба за титул видна еще до первой строки.
          </p>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border px-6 py-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Чемпионат конструкторов</p>
            <h2 className="mt-2 section-title">Баланс команд по всему сезону.</h2>
          </div>
          <p className="max-w-[54ch] text-sm leading-6 text-muted">
            Конструкторы остаются вторичным срезом: они важны для командной идентичности, но не должны затмевать
            member-first историю чемпионата.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[720px]">
            <thead>
              <tr>
                <th>Поз</th>
                <th>Команда</th>
                <th>Состав</th>
                <th className="text-right">Победы</th>
                <th className="text-right">Очки</th>
              </tr>
            </thead>
            <tbody>
              {constructors.map((entry) => (
                <tr key={entry.team_id}>
                  <td className="mono-data text-muted">P{entry.position}</td>
                  <td>
                    <div className="flex items-center gap-3">
                      <TeamColorBar color={entry.team_color} className="h-10" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-text">{entry.team_name}</p>
                        <div className="mt-3">
                          <PointsBar points={entry.total_points} maxPoints={maxConstructorPoints} color={entry.team_color} />
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="text-sm text-muted">
                    {[entry.driver_1, entry.driver_2].filter(Boolean).join(" / ") || "Состав уточняется"}
                  </td>
                  <td className="text-right mono-data text-muted">{entry.wins}</td>
                  <td className="text-right mono-data font-semibold text-text">{entry.total_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
