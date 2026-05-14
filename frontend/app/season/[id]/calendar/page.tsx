import Link from "next/link"
import { api } from "@/lib/api"
import { PageIntro } from "@/components/PageIntro"
import { formatDate } from "@/lib/utils"

export const dynamic = "force-dynamic"

export default async function SeasonCalendarPage({ params }: { params: { id: string } }) {
  const seasonId = Number(params.id)
  const calendar = await api.calendar(seasonId).catch(() => [])

  const completedRounds = calendar.filter((entry) => entry.completed).length
  const upcoming = calendar.find((entry) => !entry.completed) ?? null
  const latestCompleted = [...calendar].reverse().find((entry) => entry.completed) ?? null
  const progress = calendar.length > 0 ? Math.round((completedRounds / calendar.length) * 100) : 0

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Календарь сезона"
        title="Расписание чемпионата, читаемое как состояние, а не просто набор дат."
        description={
          <>
            Календарь работает как таймлайн сезона. Завершенные этапы ведут в детали гонки, предстоящие держат место для
            следующего перехода состояния, а архив остается рядом с обзором, а не прячется в прямых ссылках.
          </>
        }
        actions={
          <>
            <Link href={`/season/${seasonId}`} className="ui-button-secondary">
              Назад к сезону
            </Link>
            <Link href="/races" className="ui-button-tertiary">
              Архив гонок
            </Link>
          </>
        }
        meta={
          <>
            <span className="data-pill">{completedRounds}/{calendar.length} этапов завершено</span>
            <span className="data-pill">{progress}% прогресса сезона</span>
          </>
        }
      />

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Этапов завершено</p>
          <p className="stat-value mono-data">
            {completedRounds}/{calendar.length}
          </p>
          <p className="mt-2 text-sm text-muted">Прогресс чемпионата</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Следующее событие</p>
          <p className="stat-value">{upcoming?.track_name ?? "Сезон завершен"}</p>
          <p className="mt-2 text-sm text-muted">{upcoming ? `Раунд ${upcoming.round}` : "Запланированных этапов больше нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Последний результат</p>
          <p className="stat-value">{latestCompleted?.track_name ?? "Пока нет"}</p>
          <p className="mt-2 text-sm text-muted">
            {latestCompleted ? formatDate(latestCompleted.raced_at) : "История гонок начнется после первого этапа"}
          </p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Состояние календаря</p>
          <p className="stat-value">{calendar.length > 0 ? "Заполнен" : "Пуст"}</p>
          <p className="mt-2 text-sm text-muted">
            {calendar.length > 0 ? "У сезона есть видимый таймлайн и архивный маршрут." : "Добавьте этапы в инструментах оператора."}
          </p>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Таймлайн этапов</p>
          <h2 className="mt-2 section-title">Сезон это последовательность событий, а не папка с таблицами.</h2>
        </div>
        <div className="p-6">
          <div className="h-2 overflow-hidden rounded-full border border-border bg-surfaceAlt">
            <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-3 text-sm text-muted">
            {completedRounds === calendar.length && calendar.length > 0
              ? "Все запланированные этапы завершены. Переходите в историю гонок и рекорды."
              : upcoming
                ? `${upcoming.track_name} это следующий этап по календарю.`
                : "Ждем, пока календарь сезона будет настроен."}
          </p>

          <div className="mt-6 space-y-3">
            {calendar.map((entry) => (
              <div key={entry.round} className="archive-row">
                <div>
                  <p className="utility-kicker">Раунд</p>
                  <p className="mt-2 mono-data text-lg text-muted">R{entry.round}</p>
                </div>
                <div>
                  <p className="text-lg font-semibold text-text">{entry.track_name}</p>
                  <p className="mt-2 text-sm text-muted">
                    {entry.completed
                      ? `Завершен ${formatDate(entry.raced_at)} и уже проиндексирован в истории гонок.`
                      : "Запланирован и ждет загрузки после гоночного вечера."}
                  </p>
                </div>
                <div className="flex items-center justify-between gap-3 md:justify-end">
                  <span className="data-pill">{entry.completed ? "Завершен" : "Скоро"}</span>
                  {entry.race_id ? (
                    <Link href={`/race/${entry.race_id}`} className="text-sm text-info transition-colors hover:text-text">
                      Открыть гонку
                    </Link>
                  ) : (
                    <span className="text-sm text-muted">Ждем результат</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
