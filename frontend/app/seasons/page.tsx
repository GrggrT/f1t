import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"
import { formatDate } from "@/lib/utils"
import { getCurrentSeasonContext, sortSeasons } from "@/lib/site-data"
import { api } from "@/lib/api"

export const revalidate = 60

export default async function SeasonsPage() {
  const { activeSeason } = await getCurrentSeasonContext()
  const seasons = sortSeasons(await api.seasons().catch(() => []))

  return (
    <div className="page-shell">
      <PageIntro
        eyebrow="Архив сезонов"
        title="Сначала текущий сезон. Сразу под ним архив."
        description="Этот индекс нужен, чтобы быстро открыть живой чемпионат или уйти назад по завершенным сезонам. Активная кампания всегда наверху, а архив читается в той же структуре."
        actions={
          activeSeason ? (
            <Link href={`/season/${activeSeason.id}`} className="ui-button-primary">
              Текущий сезон
            </Link>
          ) : undefined
        }
        meta={
          <>
            <span className="data-pill">{seasons.length} сезонов в индексе</span>
            {activeSeason ? <span className="state-chip">{activeSeason.name}</span> : null}
          </>
        }
      />

      {activeSeason ? (
        <section className="surface-panel overflow-hidden">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_220px_230px]">
            <div className="space-y-4 p-6 sm:p-8">
              <div>
                <p className="eyebrow">Текущий сезон</p>
                <h2 className="mt-3 section-title">{activeSeason.name}</h2>
              </div>
              <p className="max-w-[58ch] text-sm leading-7 text-muted">
            Обзор сезона это главный экран для таблицы, календаря, оперативного состояния, итогов гонок и
                инженерных инструментов. Все остальные разделы ветвятся уже оттуда.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href={`/season/${activeSeason.id}`} className="ui-button-primary">
                  Обзор сезона
                </Link>
                <Link href={`/season/${activeSeason.id}/standings`} className="ui-button-secondary">
                  Таблица
                </Link>
                <Link href={`/season/${activeSeason.id}/calendar`} className="ui-button-tertiary">
                  Календарь
                </Link>
              </div>
            </div>

            <div className="border-l border-border px-6 py-6 sm:px-8">
              <p className="utility-kicker">Статус</p>
              <p className="mt-3 text-lg font-semibold text-text">{activeSeason.status === "active" ? "Активный чемпионат" : activeSeason.status}</p>
              <p className="mt-2 text-sm text-muted">
                {activeSeason.races_played}/{activeSeason.total_rounds || activeSeason.races_played} этапов завершено
              </p>
            </div>

            <div className="border-l border-border bg-black/10 px-6 py-6 sm:px-8">
              <p className="utility-kicker">Создан</p>
              <p className="mt-3 text-lg font-semibold text-text">{activeSeason.created_at ? formatDate(activeSeason.created_at) : "Текущая запись"}</p>
              <p className="mt-2 text-sm text-muted">Пока сезон активен, используйте его как основную точку навигации.</p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="list-panel">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Все сезоны</p>
          <h2 className="mt-2 section-title">Стабильный архив каждого чемпионата.</h2>
        </div>

        {seasons.length > 0 ? (
          seasons.map((season) => {
            const progress = `${season.races_played}/${season.total_rounds || season.races_played}`

            return (
              <div key={season.id} className="list-row md:grid-cols-[120px_minmax(0,1fr)_220px] md:items-center">
                <div>
                  <p className="utility-kicker">Сезон</p>
                  <p className="mt-2 mono-data text-lg text-muted">#{season.id}</p>
                </div>

                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-semibold text-text">{season.name}</h3>
                    <span className="state-chip">{season.status === "active" ? "Текущий сезон" : season.status}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {season.status === "active"
                      ? "Открывайте его первым, чтобы увидеть картину чемпионата, календарь и последние отчеты по гонкам."
                      : "Архивный сезон, где на месте сохранены таблица, итоги гонок и история игроков."}
                  </p>
                </div>

                <div className="space-y-3 md:text-right">
                  <div className="text-sm text-muted">
                    <div className="mono-data text-lg font-semibold text-text">{progress}</div>
                    <div>Этапов завершено</div>
                    <div className="mt-1">{season.created_at ? formatDate(season.created_at) : "Архивная запись"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2 md:justify-end">
                    <Link href={`/season/${season.id}`} className="ui-button-secondary h-10 px-4">
                      Обзор
                    </Link>
                    <Link href={`/season/${season.id}/standings`} className="ui-button-tertiary">
                      Таблица
                    </Link>
                  </div>
                </div>
              </div>
            )
          })
        ) : (
          <div className="px-6 py-6 text-sm text-muted">Сезоны еще не были опубликованы.</div>
        )}
      </section>
    </div>
  )
}
