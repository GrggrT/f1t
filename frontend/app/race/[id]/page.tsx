import Link from "next/link"
import { notFound } from "next/navigation"
import { PlayerBadge } from "@/components/PlayerBadge"
import { RaceNav } from "@/components/RaceNav"
import { TeamColorBar } from "@/components/TeamColorBar"
import { api, type RaceResult } from "@/lib/api"
import { formatDate, formatLapTime } from "@/lib/utils"

export const revalidate = 60

function resultTone(status: string) {
  if (status === "Finished") return "text-text"
  if (status === "DNF" || status === "Retired") return "text-amber"
  if (status === "DSQ") return "text-danger"
  return "text-muted"
}

export default async function RacePage({ params }: { params: { id: string } }) {
  const race = await api.race(Number(params.id)).catch(() => null)

  if (!race) {
    notFound()
  }

  const results = [...(race.results ?? [])].sort((a, b) => (a.position ?? 99) - (b.position ?? 99))
  const winner = results.find((entry) => entry.position === 1) ?? null
  const fastestLap = results.find((entry) => entry.has_fastest_lap) ?? null
  const dnfCount = results.filter((entry) => entry.result_status !== "Finished").length
  const bestHumanFinisher = results.find((entry) => entry.is_human && entry.position) ?? results.find((entry) => entry.is_human) ?? null
  const podium = results.filter((entry) => entry.position && entry.position <= 3)

  return (
    <div className="page-stack">
      <RaceNav raceId={race.id} seasonId={race.season_id} trackName={race.track_name} round={race.round} />

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-start">
          <div className="space-y-4">
            <p className="eyebrow">Официальный результат гонки</p>
            <h2 className="section-title">
              {winner ? `${winner.driver_name} выиграл гонку на ${race.track_name}.` : `Сводка гонки на ${race.track_name}.`}
            </h2>
            <p className="page-copy">
              {winner && fastestLap
                ? `${winner.driver_name} взял победу за ${winner.team_name}. Быстрейший круг у ${fastestLap.driver_name} с временем ${formatLapTime(fastestLap.best_lap_ms)}.`
                : "Эта страница держит вместе официальную классификацию и факты гонки до того, как вы уйдете в более глубокий анализ."}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/race/${race.id}/analysis`} className="ui-button-primary">
                Анализ
              </Link>
              <Link href={`/telemetry/${race.id}`} className="ui-button-secondary">
                Телеметрия
              </Link>
              <Link href={`/compare/${race.id}`} className="ui-button-tertiary">
                Сравнение кругов
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Факты гонки</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-lg font-semibold text-text">{formatDate(race.raced_at)}</p>
                <p className="mt-1 text-sm text-muted">Раунд {race.round ?? "--"}</p>
              </div>
              <div>
                <p className="utility-kicker">Дистанция</p>
                <p className="mt-2 text-base font-semibold text-text">{race.total_laps ? `${race.total_laps} кругов` : "Официальный результат"}</p>
              </div>
              <div>
                <p className="utility-kicker">Сезон</p>
                <Link href={`/season/${race.season_id}`} className="mt-2 inline-flex text-base font-semibold text-text transition-colors hover:text-accent">
                  Вернуться к сезону
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Победитель</p>
          <p className="stat-value">{winner?.driver_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">{winner?.team_name ?? "Результата нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Быстрейший круг</p>
          <p className="stat-value mono-data">{fastestLap ? formatLapTime(fastestLap.best_lap_ms) : "--"}</p>
          <p className="mt-2 text-sm text-muted">{fastestLap?.driver_name ?? "Эталона нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Лучший финиш человека</p>
          <p className="stat-value">{bestHumanFinisher?.driver_name ?? "Нет"}</p>
          <p className="mt-2 text-sm text-muted">
            {bestHumanFinisher?.position ? `P${bestHumanFinisher.position}` : "Нет классифицированного human-финиша"}
          </p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Сходы</p>
          <p className="stat-value mono-data">{dnfCount}</p>
          <p className="mt-2 text-sm text-muted">DNF, сход или дисквалификация</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.16fr)_360px]">
        <div className="surface-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-6 py-5">
            <div>
              <p className="eyebrow">Финишная классификация</p>
              <h2 className="mt-2 section-title">Официальная классификация.</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[760px]">
              <thead>
                <tr>
                  <th>Поз</th>
                  <th>Пилот</th>
                  <th className="text-right">Грид</th>
                  <th className="text-right">Лучший круг</th>
                  <th className="text-right">Статус</th>
                  <th className="text-right">Очки</th>
                </tr>
              </thead>
              <tbody>
                {results.map((entry) => (
                  <RaceResultRow key={entry.vehicle_index} result={entry} />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">Подиум</p>
            <div className="mt-4 space-y-3">
              {podium.length > 0 ? (
                podium.map((entry) => (
                  <div key={entry.vehicle_index} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                    <p className="mono-data text-xs uppercase tracking-[0.16em] text-dim">P{entry.position}</p>
                    <p className="mt-1 text-lg font-semibold text-text">{entry.driver_name}</p>
                    <p className="text-sm text-muted">{entry.team_name}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted">Данные по подиуму для этой гонки пока недоступны.</p>
              )}
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="eyebrow">Продолжить в</p>
            <div className="mt-4 space-y-2">
              <Link href={`/race/${race.id}/analysis`} className="ui-button-secondary w-full">
                Полный анализ
              </Link>
              <Link href={`/telemetry/${race.id}`} className="ui-button-tertiary w-full">
                Карта телеметрии
              </Link>
              <Link href={`/compare/${race.id}`} className="ui-button-tertiary w-full">
                Сравнение пилотов
              </Link>
              <Link href={`/race/${race.id}/replay`} className="ui-button-tertiary w-full">
                Повтор
              </Link>
            </div>
          </div>
        </div>
      </section>

      {race.events && race.events.length > 0 ? (
        <section className="list-panel">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Журнал событий</p>
            <h2 className="mt-2 section-title">Инциденты и структурированные события гонки.</h2>
          </div>
          {race.events.slice(0, 10).map((event, index) => (
            <div key={`${event.code}-${index}`} className="list-row md:grid-cols-[110px_90px_minmax(0,1fr)]">
              <div>
                <p className="utility-kicker">Событие</p>
                <p className="mt-2 mono-data text-lg text-muted">{event.code}</p>
              </div>
              <div>
                <p className="utility-kicker">Круг</p>
                <p className="mt-2 mono-data text-lg text-muted">{event.lap ?? "--"}</p>
              </div>
              <div className="text-sm leading-7 text-muted">{JSON.stringify(event.data)}</div>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  )
}

function RaceResultRow({ result }: { result: RaceResult }) {
  const gridDelta =
    result.grid_position && result.position && result.grid_position !== result.position
      ? result.position < result.grid_position
        ? `+${result.grid_position - result.position}`
        : `-${result.position - result.grid_position}`
      : null

  return (
    <tr className={result.is_human ? "player-row" : ""}>
      <td className="mono-data text-muted">{result.position ? `P${result.position}` : "--"}</td>
      <td>
        <div className="flex items-center gap-2">
          <TeamColorBar color={result.team_color ?? "#666"} className="h-8" />
          <div>
            <div className="flex items-center gap-2">
              {result.player_id ? (
                <Link href={`/players/${result.player_id}`} className="font-medium text-text transition-colors hover:text-accent">
                  {result.driver_name}
                </Link>
              ) : (
                <span className="font-medium text-text">{result.driver_name}</span>
              )}
              {result.is_human ? <PlayerBadge /> : null}
            </div>
            <div className="text-xs text-muted">{result.team_name}</div>
          </div>
        </div>
      </td>
      <td className="text-right mono-data text-muted">
        {result.grid_position ?? "--"}
        {gridDelta ? <span className="ml-2 text-xs text-muted">{gridDelta}</span> : null}
      </td>
      <td className="text-right mono-data text-text">{formatLapTime(result.best_lap_ms)}</td>
      <td className={`text-right text-sm ${resultTone(result.result_status)}`}>{result.result_status}</td>
      <td className="text-right mono-data font-semibold text-text">{result.points > 0 ? result.points : "--"}</td>
    </tr>
  )
}
