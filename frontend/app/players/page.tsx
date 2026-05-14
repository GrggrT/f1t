import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"
import { getCurrentSeasonContext, getPlayersDirectory } from "@/lib/site-data"

export const revalidate = 60

export default async function PlayersPage() {
  const [directory, seasonContext] = await Promise.all([getPlayersDirectory(), getCurrentSeasonContext()])
  const activeSeason = seasonContext.activeSeason
  const leader = directory[0] ?? null

  return (
    <div className="page-shell">
      <PageIntro
        eyebrow="Игроки"
        title="Участники лиги, рейтинг и место в текущем сезоне."
        description="Открывайте профили игроков из одного стабильного индекса, а не ищите их косвенно через таблицу или результаты гонок. Рейтинг задает общий порядок, а колонка текущего сезона привязывает его к живому чемпионату."
        meta={
          <>
            <span className="data-pill">{directory.length} игроков в рейтинге</span>
            {activeSeason ? <span className="state-chip">{activeSeason.name}</span> : null}
            {leader ? <span className="data-pill">Лидер рейтинга: {leader.name}</span> : null}
          </>
        }
      />

      {leader ? (
        <section className="surface-panel overflow-hidden">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_220px_220px]">
            <div className="space-y-4 p-6 sm:p-8">
              <div>
                <p className="eyebrow">Игрок с лучшим рейтингом</p>
                <h2 className="mt-3 section-title">{leader.name}</h2>
              </div>
              <p className="max-w-[58ch] text-sm leading-7 text-muted">
                {leader.standing
                  ? `Сейчас ${leader.standing.position ? `P${leader.standing.position}` : "вне классификации"} в ${activeSeason?.name ?? "текущем сезоне"} и при этом держит самый высокий опубликованный рейтинг.`
                  : "Лидирует в опубликованной рейтинговой таблице. Откройте профиль, чтобы увидеть последние гонки, историю сезонов и текущую форму."}
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href={`/players/${leader.player_id}`} className="ui-button-primary">
                  Открыть профиль
                </Link>
                {activeSeason ? (
                  <Link href={`/season/${activeSeason.id}/standings`} className="ui-button-secondary">
                    Таблица сезона
                  </Link>
                ) : null}
              </div>
            </div>

            <div className="border-l border-border px-6 py-6 sm:px-8">
              <p className="utility-kicker">Рейтинг</p>
              <p className="mt-3 mono-data text-2xl font-semibold text-text">{Math.round(leader.rating)}</p>
              <p className="mt-2 text-sm text-muted">Пик {Math.round(leader.peak_rating)}</p>
            </div>

            <div className="border-l border-border bg-black/10 px-6 py-6 sm:px-8">
              <p className="utility-kicker">Текущий сезон</p>
              <p className="mt-3 text-lg font-semibold text-text">
                {leader.standing?.position ? `P${leader.standing.position}` : activeSeason ? "Вне классификации" : "Архив"}
              </p>
              <p className="mt-2 text-sm text-muted">{leader.races_rated} рейтинговых гонок</p>
            </div>
          </div>
        </section>
      ) : null}

      <section className="surface-panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-6 py-5">
          <div>
            <p className="eyebrow">Каталог</p>
            <h2 className="mt-2 section-title">Сначала рейтинг, рядом контекст текущего сезона.</h2>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[880px]">
            <thead>
              <tr>
                <th>Место</th>
                <th>Игрок</th>
                <th className="text-right">Рейтинг</th>
                <th className="text-right">Пик</th>
                <th className="text-right">Поз. в сезоне</th>
                <th className="text-right">W/L</th>
                <th className="text-right">Профиль</th>
              </tr>
            </thead>
            <tbody>
              {directory.map((player, index) => (
                <tr key={player.player_id}>
                  <td className="mono-data text-muted">#{index + 1}</td>
                  <td>
                    <div className="flex items-center gap-3">
                      {player.avatar_url ? (
                        <img src={player.avatar_url} alt="" className="h-10 w-10 rounded-full object-cover" />
                      ) : (
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-surfaceAlt text-sm font-semibold text-accent">
                          {player.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <Link href={`/players/${player.player_id}`} className="font-medium text-text transition-colors hover:text-accent">
                          {player.name}
                        </Link>
                        <div className="text-xs text-muted">
                          {player.steam_names.length > 0 ? player.steam_names.slice(0, 2).join(" / ") : "Участник лиги"}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="text-right mono-data font-semibold text-text">{Math.round(player.rating)}</td>
                  <td className="text-right mono-data text-muted">{Math.round(player.peak_rating)}</td>
                  <td className="text-right mono-data text-muted">
                    {player.standing ? `P${player.standing.position}` : activeSeason ? "--" : "Архив"}
                  </td>
                  <td className="text-right mono-data text-muted">
                    {player.wins}/{player.losses}
                  </td>
                  <td className="text-right">
                    <Link href={`/players/${player.player_id}`} className="text-sm text-info transition-colors hover:text-text">
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
