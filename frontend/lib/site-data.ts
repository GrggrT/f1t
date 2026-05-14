import { api, type CalendarEntry, type DriverStanding, type Race, type RatingEntry, type Season, type TrackRecord } from "@/lib/api"

const BASE = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function fetchJson<T>(path: string, revalidate = 60): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { next: { revalidate } })
    if (!res.ok) {
      return null
    }

    return res.json()
  } catch {
    return null
  }
}

function seasonSortValue(season: Season) {
  return season.created_at ? new Date(season.created_at).getTime() : season.id
}

export function sortSeasons(seasons: Season[]) {
  return [...seasons].sort((a, b) => {
    const statusRank = (season: Season) => {
      if (season.status === "active") return 0
      if (season.status === "finished") return 1
      return 2
    }

    return statusRank(a) - statusRank(b) || seasonSortValue(b) - seasonSortValue(a)
  })
}

export async function getSeasonShellData() {
  const seasons = sortSeasons(await api.seasons().catch(() => []))
  const activeSeason = seasons.find((season) => season.status === "active") ?? seasons[0] ?? null

  return {
    seasons,
    activeSeason,
  }
}

export async function getPlayersList() {
  return (await fetchJson<
    {
      id: number
      name: string
      steam_names?: string[]
      avatar_url?: string | null
      telegram_id?: number | null
    }[]
  >("/api/players", 60)) ?? []
}

export async function getCurrentSeasonContext() {
  const { seasons, activeSeason } = await getSeasonShellData()

  if (!activeSeason) {
    return {
      seasons,
      activeSeason: null as Season | null,
      standings: [] as DriverStanding[],
      calendar: [] as CalendarEntry[],
      races: [] as Race[],
      ratings: [] as RatingEntry[],
      records: [] as TrackRecord[],
    }
  }

  const [standings, calendar, races, ratings, records] = await Promise.all([
    api.standings(activeSeason.id).catch(() => []),
    api.calendar(activeSeason.id).catch(() => []),
    api.races(activeSeason.id).catch(() => []),
    api.ratings().catch(() => []),
    api.records(activeSeason.id).catch(() => []),
  ])

  return {
    seasons,
    activeSeason,
    standings,
    calendar,
    races,
    ratings,
    records,
  }
}

export async function getSeasonOverviewBundle(seasonId: number) {
  const [season, standings, constructors, calendar, races, records, contracts] = await Promise.all([
    api.season(seasonId).catch(() => null),
    api.standings(seasonId).catch(() => []),
    api.constructors(seasonId).catch(() => []),
    api.calendar(seasonId).catch(() => []),
    api.races(seasonId).catch(() => []),
    api.records(seasonId).catch(() => []),
    api.contracts(seasonId).catch(() => []),
  ])

  return { season, standings, constructors, calendar, races, records, contracts }
}

export async function getRaceArchive() {
  const seasons = sortSeasons(await api.seasons().catch(() => []))
  const seasonRaces = await Promise.all(
    seasons.map(async (season) => ({
      season,
      races: await api.races(season.id).catch(() => []),
    })),
  )

  return seasonRaces
    .flatMap(({ season, races }) =>
      races.map((race) => ({
        ...race,
        seasonName: season.name,
        seasonStatus: season.status,
      })),
    )
    .sort((a, b) => new Date(b.raced_at).getTime() - new Date(a.raced_at).getTime() || b.id - a.id)
}

export async function getPlayersDirectory() {
  const [players, ratings, seasons] = await Promise.all([getPlayersList(), api.ratings().catch(() => []), api.seasons().catch(() => [])])

  const activeSeason = sortSeasons(seasons).find((season) => season.status === "active") ?? seasons[0] ?? null
  const standings = activeSeason ? await api.standings(activeSeason.id).catch(() => []) : []
  const standingByPlayerId = new Map(standings.filter((item) => item.player_id).map((item) => [item.player_id as number, item]))
  const playerById = new Map(players.map((player) => [player.id, player]))

  return ratings
    .map((rating) => {
      const player = playerById.get(rating.player_id)
      const standing = standingByPlayerId.get(rating.player_id)

      return {
        ...rating,
        avatar_url: player?.avatar_url ?? null,
        steam_names: player?.steam_names ?? [],
        standing,
      }
    })
    .sort((a, b) => b.rating - a.rating || b.peak_rating - a.peak_rating)
}
