import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"
import { api } from "@/lib/api"
import { getCurrentSeasonContext } from "@/lib/site-data"
import { formatLapTime } from "@/lib/utils"

export const revalidate = 300

export default async function RecordsPage() {
  const { activeSeason } = await getCurrentSeasonContext()
  const seasonId = activeSeason?.id ?? 1
  const [records, funStats, achievements] = await Promise.all([
    api.records(seasonId).catch(() => []),
    api.funStats(seasonId).catch(() => []),
    api.achievements(seasonId).catch(() => []),
  ])

  const leadingRecord = records[0] ?? null
  const leadingAchievement = achievements[0] ?? null

  return (
    <div className="page-shell">
      <PageIntro
        eyebrow="Книга рекордов"
        title="Рекорды"
        description="Книга рекордов собирает быстрые круги, сезонные суперлативы и историю достижений в одном месте."
        meta={
          <>
            <span className="data-pill">{records.length} эталонов по трассам</span>
            <span className="data-pill">{achievements.length} открытых достижений</span>
            {leadingRecord ? <span className="state-chip">{leadingRecord.track_name}</span> : null}
          </>
        }
      />

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Главный ориентир</p>
          <p className="stat-value mono-data">{leadingRecord ? formatLapTime(leadingRecord.best_lap_ms) : "--"}</p>
          <p className="mt-2 text-sm text-muted">{leadingRecord ? `${leadingRecord.track_name} | ${leadingRecord.driver_name}` : "Рекордов пока нет"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Моменты сезона</p>
          <p className="stat-value mono-data">{funStats.length}</p>
          <p className="mt-2 text-sm text-muted">Именованные суперлативы сезона</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Журнал достижений</p>
          <p className="stat-value mono-data">{achievements.length}</p>
          <p className="mt-2 text-sm text-muted">{leadingAchievement ? leadingAchievement.player_name : "Ждем первые открытия"}</p>
        </div>
      </section>

      {funStats.length > 0 ? (
        <section className="surface-panel p-6">
          <p className="eyebrow">Суперлативы сезона</p>
          <h2 className="mt-2 section-title">Запоминающиеся паттерны, к которым стоит возвращаться.</h2>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {funStats.map((stat, index) => (
              <div key={`${stat.title}-${index}`} className="surface-panel-muted p-4">
                <p className="utility-kicker">{stat.title}</p>
                <p className="mt-2 text-lg font-semibold text-text">{stat.player_name}</p>
                <p className="mt-2 text-sm text-muted">{stat.value}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Рекорды трасс</p>
          <h2 className="mt-2 section-title">Опубликованные быстрые круги.</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Трасса</th>
                <th>Пилот</th>
                <th className="text-right">Эталон</th>
                <th className="text-right">Гонка</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.track_id}>
                  <td className="font-medium text-text">{record.track_name}</td>
                  <td className="text-muted">{record.driver_name}</td>
                  <td className="text-right mono-data font-semibold text-text">{formatLapTime(record.best_lap_ms)}</td>
                  <td className="text-right">
                    <Link href={`/race/${record.race_id}`} className="text-sm text-info transition-colors hover:text-text">
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
        <p className="eyebrow">Журнал достижений</p>
        <h2 className="mt-2 section-title">Открытые карьерные метки.</h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {achievements.length > 0 ? (
            achievements.map((achievement, index) => (
              <div key={`${achievement.player_name}-${index}`} className="surface-panel-muted p-4">
                <p className="text-base font-semibold text-text">{achievement.ach_name}</p>
                <p className="mt-2 text-sm leading-7 text-muted">{achievement.ach_desc}</p>
                <p className="mt-3 text-sm text-text">{achievement.player_name}</p>
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
