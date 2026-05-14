import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"
import { formatDate, formatLapTime } from "@/lib/utils"
import { getCurrentSeasonContext } from "@/lib/site-data"

export const revalidate = 30

function seasonStatusLabel(status: string) {
  if (status === "active") return "Текущий сезон"
  if (status === "finished") return "Завершенный сезон"
  return "Архив сезона"
}

export default async function HomePage() {
  const { activeSeason, standings, calendar, races, ratings, records } = await getCurrentSeasonContext()

  const humanStandings = standings.filter((entry) => entry.is_human)
  const completedRounds = calendar.filter((entry) => entry.completed).length
  const nextRace = calendar.find((entry) => !entry.completed) ?? null
  const latestRace = [...races].sort((a, b) => b.round - a.round)[0] ?? null
  const recentRaces = [...races].sort((a, b) => b.round - a.round).slice(0, 4)
  const leader = humanStandings[0] ?? null
  const runnerUp = humanStandings[1] ?? null
  const topPlayers = ratings.slice(0, 5)
  const headlineRecord = records[0] ?? null
  const seasonProgressTotal = calendar.length || activeSeason?.total_rounds || 0
  const titleFightGap = leader && runnerUp ? leader.total_points - runnerUp.total_points : null

  if (!activeSeason) {
    return (
      <div className="page-shell">
        <PageIntro
          eyebrow="Сайт лиги"
          title="Сезонный центр уже готов."
          description="Сайт уже работает как публичный реестр лиги: таблица, итоги гонок, профили игроков и установка лаунчера собраны в одном месте. Опубликуйте сезон или войдите по инвайту, чтобы запустить живую оболочку чемпионата."
          actions={
            <>
              <Link href="/launcher" className="ui-button-primary">
                Установить лаунчер
              </Link>
              <Link href="/lobby/join" className="ui-button-secondary">
                Вступить по инвайту
              </Link>
            </>
          }
          meta={
            <>
              <span className="state-chip">Нет активного сезона</span>
              <span className="data-pill">Публичный архив</span>
              <span className="data-pill">Профили игроков</span>
              <span className="data-pill">Windows-лаунчер</span>
            </>
          }
        />
      </div>
    )
  }

  return (
    <div className="page-shell">
      <section className="surface-feature overflow-hidden">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1.18fr)_360px]">
          <div className="space-y-8 p-6 sm:p-8 lg:p-10">
            <div className="flex flex-wrap items-center gap-2">
              <span className="state-chip">{seasonStatusLabel(activeSeason.status)}</span>
              <span className="data-pill">{completedRounds}/{seasonProgressTotal} этапов завершено</span>
              {leader ? <span className="data-pill">Лидер: {leader.driver_name}</span> : null}
            </div>

            <div className="space-y-4">
              <p className="eyebrow">Текущий сезон</p>
              <h1 className="page-title">{activeSeason.name}</h1>
              <p className="max-w-[58ch] text-lg leading-8 text-muted sm:text-[1.08rem]">
                {leader && runnerUp
                  ? `${leader.driver_name} опережает ${runnerUp.driver_name} на ${leader.total_points - runnerUp.total_points} очков после ${completedRounds} завершенных этапов.`
                  : "Здесь публикуются таблица, календарь, итоги гонок и профили игроков по мере развития сезона."}
              </p>
              <p className="page-copy">
                Это в первую очередь главный экран лиги, а уже потом продуктовая витрина: откройте обзор сезона, чтобы увидеть
                картину чемпионата, архив гонок для опубликованных результатов или лаунчер, если нужен локальный захват телеметрии.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link href={`/season/${activeSeason.id}`} className="ui-button-primary">
                Обзор сезона
              </Link>
              <Link href={`/season/${activeSeason.id}/standings`} className="ui-button-secondary">
                Таблица
              </Link>
              <Link href="/launcher" className="ui-button-tertiary">
                Установить лаунчер
              </Link>
            </div>

            <div className="summary-grid">
              <div className="stat-card">
                <p className="stat-label">Лидер сезона</p>
                <p className="stat-value">{leader?.driver_name ?? "Ожидается"}</p>
                <p className="mt-2 text-sm text-muted">{leader ? `${leader.total_points} очков` : "Ждем первый опубликованный результат"}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Разрыв в борьбе за титул</p>
                <p className="stat-value mono-data">{titleFightGap ?? "--"}</p>
                <p className="mt-2 text-sm text-muted">{runnerUp ? `до ${runnerUp.driver_name}` : "Пока нет второго места"}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Следующий этап</p>
                <p className="stat-value">{nextRace?.track_name ?? "Сезон завершен"}</p>
                <p className="mt-2 text-sm text-muted">{nextRace ? `Раунд ${nextRace.round}` : "Архив остается доступным"}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Последний отчет</p>
                <p className="stat-value">{latestRace?.track_name ?? "Гонок еще нет"}</p>
                <p className="mt-2 text-sm text-muted">{latestRace ? formatDate(latestRace.raced_at) : "Появится после первой загрузки"}</p>
              </div>
            </div>
          </div>

          <div className="border-l border-border bg-black/10 p-6 sm:p-8">
            <div className="space-y-5">
              <div className="surface-panel p-5">
                <p className="utility-kicker">Сайт лиги</p>
                <p className="mt-3 text-lg font-semibold text-text">Текущий сезон, архив гонок и история игроков собраны в одном опубликованном реестре.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="data-pill">Архив сезонов</span>
                  <span className="data-pill">Итоги гонок</span>
                  <span className="data-pill">Профили игроков</span>
                </div>
              </div>

              <div className="surface-panel p-5">
                <p className="utility-kicker">Следующий запланированный этап</p>
                <p className="mt-3 text-xl font-semibold text-text">{nextRace?.track_name ?? "Сезон завершен"}</p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {nextRace
                    ? `Раунд ${nextRace.round} станет следующей точкой, где обновятся таблица, загрузки и оперативные инструменты.`
                    : "Все запланированные этапы уже опубликованы. Используйте архив, чтобы разобрать завершенный сезон."}
                </p>
              </div>

              <div className="surface-panel p-5">
                <p className="utility-kicker">Роль лаунчера</p>
                <p className="mt-3 text-xl font-semibold text-text">Устанавливайте его только когда нужен захват.</p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  Для обычного просмотра сайта десктопное приложение не требуется. Лаунчер нужен для захвата телеметрии, загрузки данных и операторских действий в гоночный вечер.
                </p>
                <div className="mt-4">
                  <Link href="/launcher" className="ui-button-secondary w-full">
                    Настроить лаунчер
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.16fr)_360px]">
        <div className="surface-panel overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-border px-6 py-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="eyebrow">Таблица сезона</p>
              <h2 className="mt-2 section-title">Порядок чемпионата стоит выше любых вторичных деталей.</h2>
            </div>
            <Link href={`/season/${activeSeason.id}/standings`} className="ui-button-tertiary">
              Полная таблица
            </Link>
          </div>
          <div className="overflow-x-auto p-6">
            <table className="data-table min-w-[720px]">
              <thead>
                <tr>
                  <th>Поз</th>
                  <th>Пилот</th>
                  <th className="text-right">Победы</th>
                  <th className="text-right">Подиумы</th>
                  <th className="text-right">Очки</th>
                </tr>
              </thead>
              <tbody>
                {humanStandings.slice(0, 8).map((entry) => (
                  <tr key={entry.driver_id}>
                    <td className="mono-data text-muted">P{entry.position}</td>
                    <td>
                      <div className="font-medium text-text">{entry.driver_name}</div>
                      <div className="text-xs text-muted">{entry.team_name}</div>
                    </td>
                    <td className="text-right mono-data text-muted">{entry.wins}</td>
                    <td className="text-right mono-data text-muted">{entry.podiums}</td>
                    <td className="text-right mono-data font-semibold text-text">{entry.total_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Прогресс сезона</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-lg font-semibold text-text">{completedRounds}/{seasonProgressTotal} этапов завершено</p>
                <p className="mt-1 text-sm text-muted">Обзор сезона остается главным экраном для таблицы, календаря и оперативного состояния.</p>
              </div>
              {nextRace ? (
                <div>
                  <p className="utility-kicker">Следующий этап</p>
                  <p className="mt-2 text-base font-semibold text-text">{nextRace.track_name}</p>
                  <p className="mt-1 text-sm text-muted">Раунд {nextRace.round}</p>
                </div>
              ) : null}
              {latestRace ? (
                <div>
                  <p className="utility-kicker">Последняя опубликованная гонка</p>
                  <Link href={`/race/${latestRace.id}`} className="mt-2 inline-flex text-base font-semibold text-text transition-colors hover:text-accent">
                    {latestRace.track_name}
                  </Link>
                  <p className="mt-1 text-sm text-muted">{formatDate(latestRace.raced_at)}</p>
                </div>
              ) : null}
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Книга рекордов</p>
            {headlineRecord ? (
              <div className="mt-4 space-y-2">
                <p className="text-lg font-semibold text-text">{headlineRecord.track_name}</p>
                <p className="mono-data text-2xl font-semibold text-text">{formatLapTime(headlineRecord.best_lap_ms)}</p>
                <p className="text-sm text-muted">{headlineRecord.driver_name}</p>
                <Link href={`/race/${headlineRecord.race_id}`} className="inline-flex text-sm text-info transition-colors hover:text-text">
                  Открыть сводку гонки
                </Link>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted">Рекорды появятся здесь после публикации первого эталонного круга.</p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
        <div className="list-panel">
          <div className="flex flex-col gap-3 border-b border-border px-6 py-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="eyebrow">Архив гонок</p>
              <h2 className="mt-2 section-title">Последние опубликованные отчеты текущего сезона.</h2>
            </div>
            <Link href="/races" className="ui-button-tertiary">
              Весь архив
            </Link>
          </div>
          {recentRaces.length > 0 ? (
            recentRaces.map((race) => (
              <div key={race.id} className="list-row md:grid-cols-[90px_minmax(0,1fr)_180px] md:items-center">
                <div>
                  <p className="utility-kicker">Раунд</p>
                  <p className="mt-2 mono-data text-lg text-muted">R{race.round}</p>
                </div>
                <div>
                  <p className="text-lg font-semibold text-text">{race.track_name}</p>
                  <p className="mt-1 text-sm text-muted">{formatDate(race.raced_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  <Link href={`/race/${race.id}`} className="ui-button-secondary h-10 px-4">
                    Сводка гонки
                  </Link>
                  <Link href={`/race/${race.id}/analysis`} className="ui-button-tertiary">
                    Анализ
                  </Link>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-6 text-sm text-muted">Архив заполнится, как только начнут публиковаться гонки.</div>
          )}
        </div>

        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Игроки</p>
            <h2 className="mt-2 section-title">Профили, рейтинг и текущая форма.</h2>
          </div>
          <div className="space-y-4 p-6">
            {topPlayers.map((player, index) => (
              <div key={player.player_id} className="flex items-center justify-between gap-4 border-b border-border pb-4 last:border-b-0 last:pb-0">
                <div>
                  <p className="mono-data text-xs uppercase tracking-[0.16em] text-dim">#{index + 1}</p>
                  <Link href={`/players/${player.player_id}`} className="mt-1 inline-flex text-lg font-semibold text-text transition-colors hover:text-accent">
                    {player.name}
                  </Link>
                  <p className="mt-1 text-sm text-muted">{player.races_rated} рейтинговых гонок</p>
                </div>
                <div className="text-right">
                  <p className="mono-data text-lg font-semibold text-text">{Math.round(player.rating)}</p>
                  <p className="text-xs text-muted">Пик {Math.round(player.peak_rating)}</p>
                </div>
              </div>
            ))}
            <div className="pt-2">
              <Link href="/players" className="ui-button-secondary w-full">
                Открыть игроков
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="surface-panel p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_340px] lg:items-start">
          <div className="space-y-4">
            <p className="eyebrow">Windows-лаунчер</p>
            <h2 className="section-title">Лаунчер нужен для захвата и загрузки, а не для обычного просмотра сайта.</h2>
            <p className="page-copy">
              Лаунчер это десктопный мост для захвата телеметрии, авторизованной загрузки и операторских действий со стороны хоста.
              Сайт при этом остается опубликованным слоем для текущего сезона, итогов гонок, профилей игроков и архива.
            </p>
            <div className="definition-list">
              <div className="definition-row">
                <span className="mono-data text-text">Платформа</span>
                <span className="text-muted">Десктопное приложение для Windows 10/11</span>
              </div>
              <div className="definition-row">
                <span className="mono-data text-text">Телеметрия</span>
                <span className="text-muted">Локальный UDP-захват из F1 25 на 127.0.0.1:20777</span>
              </div>
              <div className="definition-row">
                <span className="mono-data text-text">Сценарий</span>
                <span className="text-muted">Личный захват практики или операторская загрузка в гоночный вечер</span>
              </div>
            </div>
          </div>

          <div className="surface-panel-muted p-5">
            <p className="utility-kicker">Следующий шаг</p>
            <div className="mt-3 space-y-3">
              <Link href="/launcher" className="ui-button-primary w-full">
                Настройка лаунчера
              </Link>
              <Link href="/login" className="ui-button-secondary w-full">
                Войти
              </Link>
            </div>
            <p className="mt-4 text-sm leading-6 text-muted">
              Устанавливайте его, когда будете готовы загружать данные. В остальных случаях начинайте с обзора сезона, архива гонок или каталога игроков.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
