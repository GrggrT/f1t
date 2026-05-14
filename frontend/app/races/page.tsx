import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"
import { formatDate } from "@/lib/utils"
import { getRaceArchive } from "@/lib/site-data"

export const revalidate = 60

export default async function RacesPage() {
  const races = await getRaceArchive()
  const latestRace = races[0] ?? null

  return (
    <div className="page-shell">
      <PageIntro
        eyebrow="Архив гонок"
        title="Опубликованные отчеты о гонках, сначала самые новые."
        description="Каждая гонка открывается с одной и той же публичной сводки, а уже потом ведет в анализ, телеметрию, сравнение кругов или повтор. Архив нужен для нормальной навигации, а не для охоты за прямыми ссылками."
        actions={
          latestRace ? (
            <Link href={`/race/${latestRace.id}`} className="ui-button-primary">
              Последняя гонка
            </Link>
          ) : undefined
        }
        meta={
          <>
            <span className="data-pill">{races.length} гонок в индексе</span>
            {latestRace ? <span className="state-chip">{latestRace.track_name}</span> : null}
          </>
        }
      />

      {latestRace ? (
        <section className="surface-panel overflow-hidden">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_230px_240px]">
            <div className="space-y-4 p-6 sm:p-8">
              <div>
                <p className="eyebrow">Последняя опубликованная гонка</p>
                <h2 className="mt-3 section-title">{latestRace.track_name}</h2>
              </div>
              <p className="max-w-[58ch] text-sm leading-7 text-muted">
                Начинайте здесь с официальной классификации, а уже потом переходите в анализ и телеметрию, только если нужен
                более глубокий разбор.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href={`/race/${latestRace.id}`} className="ui-button-primary">
                  Сводка гонки
                </Link>
                <Link href={`/race/${latestRace.id}/analysis`} className="ui-button-secondary">
                  Анализ
                </Link>
                <Link href={`/telemetry/${latestRace.id}`} className="ui-button-tertiary">
                  Телеметрия
                </Link>
              </div>
            </div>

            <div className="border-l border-border px-6 py-6 sm:px-8">
              <p className="utility-kicker">Сезон</p>
              <p className="mt-3 text-lg font-semibold text-text">{latestRace.seasonName}</p>
              <p className="mt-2 text-sm text-muted">{latestRace.seasonStatus === "active" ? "Текущий сезон" : latestRace.seasonStatus}</p>
            </div>

            <div className="border-l border-border bg-black/10 px-6 py-6 sm:px-8">
              <p className="utility-kicker">Дата гонки</p>
              <p className="mt-3 text-lg font-semibold text-text">{formatDate(latestRace.raced_at)}</p>
              <p className="mt-2 text-sm text-muted">{latestRace.total_laps ? `${latestRace.total_laps} кругов` : "Официальный результат"}</p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="list-panel">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Список архива</p>
          <h2 className="mt-2 section-title">Все индексированные гонки в одном списке.</h2>
        </div>

        {races.length > 0 ? (
          races.map((race) => (
            <div key={race.id} className="list-row md:grid-cols-[110px_minmax(0,1fr)_250px] md:items-center">
              <div>
                <p className="utility-kicker">Раунд</p>
                <p className="mt-2 mono-data text-lg text-muted">R{race.round}</p>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-lg font-semibold text-text">{race.track_name}</h3>
                  <span className="data-pill">{race.seasonName}</span>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {formatDate(race.raced_at)}
                  {race.total_laps ? `  |  ${race.total_laps} кругов` : ""}
                </p>
              </div>

              <div className="flex flex-wrap gap-2 md:justify-end">
                <Link href={`/race/${race.id}`} className="ui-button-secondary h-10 px-4">
                  Сводка гонки
                </Link>
                <Link href={`/race/${race.id}/analysis`} className="ui-button-tertiary">
                  Анализ
                </Link>
                <Link href={`/telemetry/${race.id}`} className="ui-button-tertiary">
                  Телеметрия
                </Link>
              </div>
            </div>
          ))
        ) : (
          <div className="px-6 py-6 text-sm text-muted">Гонки пока недоступны.</div>
        )}
      </section>
    </div>
  )
}
