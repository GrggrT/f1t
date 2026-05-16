// Server-side → API_URL=http://backend:8000 (Docker internal)
// Client-side → NEXT_PUBLIC_API_URL=http://192.168.0.114:8000
const BASE = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 10 } })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TyreStint  { compound: string; laps: number }
export interface RaceResult {
  vehicle_index:   number
  is_human:        boolean
  player_id:       number | null
  driver_id:       number
  driver_name:     string
  team_id:         number
  team_name:       string
  team_color?:     string
  grid_position:   number | null
  position:        number | null
  points:          number
  result_status:   string
  best_lap_ms:     number | null
  penalties_time:  number | null
  num_pit_stops:   number | null
  tyre_stints:     TyreStint[]
  has_fastest_lap: boolean
}

export interface RaceEvent { code: string; data: Record<string, unknown>; lap: number | null }

export interface Race {
  id:            number
  season_id:     number
  round:         number
  track_id:      number
  track_name:    string
  raced_at:      string
  total_laps:    number | null
  weather_start: number | null
  weather_end:   number | null
  results?:      RaceResult[]
  events?:       RaceEvent[]
}

export interface DriverStanding {
  position:     number
  driver_id:    number
  driver_name:  string
  team_id:      number
  team_name:    string
  team_color:   string
  player_id:    number | null
  is_human:     boolean
  total_points: number
  wins:         number
  podiums:      number
  fastest_laps: number
  dnfs:         number
  best_finish:  number | null
}

export interface ConstructorStanding {
  position:     number
  team_id:      number
  team_name:    string
  team_color:   string
  total_points: number
  wins:         number
  driver_1:     string | null
  driver_2:     string | null
}

export interface CalendarEntry {
  round:      number
  track_id:   number
  track_name: string
  completed:  boolean
  race_id:    number | null
  raced_at:   string | null
}

// Sprint 2 / PR 2.4 — unified identity. After PR 2.5 this becomes the only
// user-shaped type; for now `WebMe` is kept as an alias so legacy pages can
// import either name without breaking. `legacy_player_id` and
// `legacy_web_user_id` carry the old IDs for any code that still needs to
// JOIN against pre-migration tables.
export interface User {
  id:                  number
  email:               string | null
  name:                string
  avatar_url:          string | null
  telegram_id:         number | null
  steam_id64:          string | null
  steam_names:         string[] | null
  is_system_admin:     boolean
  // Back-compat fields that mirror legacy WebMe shape — populated server-side
  // until PR 2.5 drops them. Treat `player_id` as "is this user linked to a
  // bot/race-data Player profile?".
  player_id:           number | null
  picture:             string | null
  player?: {
    id:           number
    name:         string
    steam_url:    string | null
    telegram_id:  number | null
    steam_names:  string[]
    avatar_url:   string | null
  }
  legacy_player_id?:   number | null
  legacy_web_user_id?: number | null
}

export type WebMe = User

export interface PlayerStats {
  player_id:    number
  name:         string
  total_points: number
  races:        number
  wins:         number
  podiums:      number
  dnfs:         number
  fastest_laps: number
  avg_position: number | null
  best_finish:  number | null
  race_history: {
    race_id:     number
    round:       number | null
    track_name:  string | null
    position:    number | null
    points:      number
    driver_name: string
    team_name:   string
  }[]
}

export interface Achievement {
  player_name: string
  ach_name:    string
  ach_icon:    string
  ach_desc:    string
  unlocked_at: string
}

export interface TrackRecord {
  track_id:    number
  track_name:  string
  best_lap_ms: number
  driver_name: string
  player_name: string | null
  race_id:     number
}

export interface FunStat {
  title:       string
  icon:        string
  player_name: string
  value:       string | number
  desc?:       string
}

export interface TelemetrySample {
  t: number; x: number; z: number
  spd: number; thr: number; brk: number
  gear: number; drs: number; dist: number
  ers?: number; str?: number; fuel?: number; tw?: number
}

export interface LapSectorData {
  lap: number; time_ms: number
  s1_ms: number; s2_ms: number; s3_ms: number
  valid: boolean
}

export interface RaceAnalysisDriver {
  vehicle_index: number; driver_name: string; team_name: string
  team_color: string; is_human: boolean
  position: number | null; grid_position: number | null
  best_lap_ms: number | null; theoretical_best_ms: number | null
  best_sectors: { s1: number | null; s2: number | null; s3: number | null }
  tyre_stints: { compound: string; laps: number }[]
  num_pit_stops: number; result_status: number; points: number
  laps: LapSectorData[]
}

export interface RaceAnalysis {
  race_id: number; track_name: string; total_laps: number | null
  weather_start: number | null; weather_end: number | null
  drivers: RaceAnalysisDriver[]
}

export interface FullProfile {
  player_id: number
  name: string
  avatar_url: string | null
  steam_url: string | null
  created_at: string | null
  current_team: string | null
  current_driver: string | null
  stats: {
    races: number; total_points: number; wins: number; podiums: number
    dnfs: number; fastest_laps: number; avg_position: number | null
    best_finish: number | null; win_rate: number; podium_rate: number
    avg_grid_delta: number | null; best_recovery: number | null; worst_drop: number | null
  }
  rating: { rating: number; rd: number; peak_rating: number; races_rated: number }
  achievements: { code: string; name: string; description: string; icon: string; unlocked_at: string | null }[]
  season_history: {
    season_id: number; season_name: string; status: string; position: number | null
    points: number; wins: number; podiums: number; fastest_laps: number; dnfs: number
    consistency_index: number | null; avg_grid_delta: number | null; team_name: string | null
  }[]
}

export interface TrendPoint {
  race_id: number; season_id: number; round: number | null; track: string | null
  position: number | null; grid_position: number | null; grid_delta: number | null
  points: number; points_cumulative: number; avg_position: number | null
  has_fastest_lap: boolean; result_status: number
}

export interface H2HData {
  player_1: { id: number; name: string }
  player_2: { id: number; name: string }
  races_together: number
  race_wins: { p1: number; p2: number }
  quali_wins: { p1: number; p2: number }
  avg_position: { p1: number | null; p2: number | null }
  total_points: { p1: number; p2: number }
  races: { race_id: number; round: number | null; track: string | null; p1_pos: number | null; p2_pos: number | null; p1_grid: number | null; p2_grid: number | null; p1_points: number; p2_points: number }[]
}

export interface RatingEntry {
  player_id: number; name: string; rating: number; rd: number
  peak_rating: number; wins: number; losses: number; races_rated: number
}

export interface RatingHistoryPoint {
  race_id: number; season_id: number; round: number; track: string
  rating_before: number; rating_after: number; change: number
}

export interface TelemetryLap {
  vehicle_index: number
  lap_number:    number
  lap_time_ms:   number | null
  samples:       TelemetrySample[]
}

export interface TelemetryDriver {
  vehicle_index: number
  driver_name:   string
  team_color:    string
  is_human:      boolean
  laps:          { lap: number; lap_ms: number | null }[]
}

export interface Season {
  id:           number
  name:         string
  status:       string
  lobby_id:     number | null
  races_played: number
  total_rounds: number
  created_at:   string | null
}

export interface LobbyInfo {
  id:            number
  name:          string
  description:   string | null
  avatar_url:    string | null
  creator_id:    number
  creator_name:  string | null
  invite_code:   string | null
  members_count: number
  seasons:       { id: number; name: string; status: string; races_played: number; total_rounds: number }[]
  your_role:     string
  created_at:    string | null
}

export interface LobbyListItem {
  id:          number
  name:        string
  description: string | null
  avatar_url:  string | null
  your_role?:  string
  members:     number
  seasons:     number
  created_at:  string | null
}

export interface LobbyMember {
  web_user_id: number
  name:        string
  picture:     string | null
  role:        string
  joined_at:   string | null
}

export interface ContractOffer {
  tier:      string
  team_id:   number
  team_name: string
  team_color: string
  narrative: string
}

export interface PlayerContracts {
  player_id:    number
  player_name:  string
  rating:       number
  current_team: string
  offers:       ContractOffer[]
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

// ── Authenticated request helpers ──

async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

async function authGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Authorization": `Bearer ${token}` },
    cache: "no-store",
  })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function authPost<T>(path: string, body: Record<string, unknown>, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

async function authPut<T>(path: string, body: Record<string, unknown>, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} → ${res.status}`)
  return res.json()
}

async function authPatch<T>(path: string, body: Record<string, unknown>, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`)
  return res.json()
}

async function authDelete<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: { "Authorization": `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`)
  return res.json()
}

export const api = {
  // Lobby (authenticated)
  lobbies:          (token?: string)           => token ? authGet<LobbyListItem[]>(`/api/lobby`, token) : get<LobbyListItem[]>(`/api/lobby`),
  lobby:            (id: number, token?: string) => token ? authGet<LobbyInfo>(`/api/lobby/${id}`, token) : get<LobbyInfo>(`/api/lobby/${id}`),
  lobbyMembers:     (id: number)               => get<LobbyMember[]>(`/api/lobby/${id}/members`),
  lobbySeasons:     (id: number)               => get<Season[]>(`/api/lobby/${id}/seasons`),
  createLobby:      (name: string, token: string, description?: string) => authPost<{ id: number; name: string; invite_code: string }>(`/api/lobby`, { name, description }, token),
  joinLobby:        (code: string, token: string) => authPost<{ ok: boolean; lobby_id: number }>(`/api/lobby/join-by-code`, { invite_code: code }, token),
  createLobbySeason: (lobbyId: number, name: string, token: string) => authPost<{ id: number; name: string }>(`/api/lobby/${lobbyId}/seasons`, { name }, token),
  leaveLobby:       (lobbyId: number, token: string) => authDelete<{ ok: boolean }>(`/api/lobby/${lobbyId}/leave`, token),
  changeRole:       (lobbyId: number, uid: number, newRole: string, token: string) => authPatch<{ ok: boolean }>(`/api/lobby/${lobbyId}/members/${uid}/role`, { new_role: newRole }, token),
  kickMember:       (lobbyId: number, uid: number, token: string) => authDelete<{ ok: boolean }>(`/api/lobby/${lobbyId}/members/${uid}`, token),
  updateLobbySettings: (lobbyId: number, body: Record<string, unknown>, token: string) => authPut<{ ok: boolean }>(`/api/lobby/${lobbyId}/settings`, body, token),
  resetInvite:      (lobbyId: number, token: string) => authPost<{ ok: boolean; invite_code: string }>(`/api/lobby/${lobbyId}/invite/reset`, {}, token),
  engineerContext:  (lobbyId: number, token: string, seasonId?: number) => authGet<any>(`/api/lobby/${lobbyId}/engineer${seasonId ? `?season_id=${seasonId}` : ''}`, token),
  engineerAsk:      (lobbyId: number, question: string, token: string, seasonId?: number) => authPost<{ answer: string }>(`/api/lobby/${lobbyId}/engineer/ask`, { question, season_id: seasonId }, token),
  linkPlayer:       (playerId: number, token: string) => authPost<{ ok: boolean; player_name: string }>(`/api/web/link-player`, { player_id: playerId }, token),
  launcherAuth:     (pollId: string, token: string) => authPost<{ ok: boolean }>(`/api/web/launcher/auth`, { poll_id: pollId }, token),
  meProfile:        (userId: number, token: string) => authGet<any>(`/api/web/me/${userId}`, token),

  // Race / Season
  race:             (id: number)               => get<Race>(`/api/race/${id}`),
  races:            (seasonId: number)         => get<Race[]>(`/api/races/${seasonId}`),
  standings:        (seasonId: number)         => get<DriverStanding[]>(`/api/standings/${seasonId}`),
  constructors:     (seasonId: number)         => get<ConstructorStanding[]>(`/api/constructors/${seasonId}`),
  playerStats:      (playerId: number)         => get<PlayerStats>(`/api/player/${playerId}/stats`),
  calendar:         (seasonId: number)         => get<CalendarEntry[]>(`/api/calendar/${seasonId}`),
  achievements:     (seasonId: number)         => get<Achievement[]>(`/api/achievements/${seasonId}`),
  records:          (seasonId: number)         => get<TrackRecord[]>(`/api/records/${seasonId}`),
  funStats:         (seasonId: number)         => get<FunStat[]>(`/api/fun_stats/${seasonId}`),
  telemetry:        (raceId: number)           => get<TelemetryDriver[]>(`/api/telemetry/${raceId}`),
  telemetryLap:     (raceId: number, v: number, lap: number) => get<TelemetryLap>(`/api/telemetry/${raceId}/${v}/${lap}`),
  telemetryBest:    (raceId: number, v: number) => get<TelemetryLap>(`/api/telemetry/${raceId}/${v}/best`),
  telemetryCompare: (raceId: number, a: number, b: number) => get<{ a: TelemetryLap & { driver_name: string; team_color: string }; b: TelemetryLap & { driver_name: string; team_color: string } }>(`/api/telemetry/${raceId}/compare?a=${a}&b=${b}`),
  raceAnalysis:     (raceId: number)           => get<RaceAnalysis>(`/api/telemetry/race-analysis/${raceId}`),
  contracts:        (seasonId: number)         => get<PlayerContracts[]>(`/api/contracts/${seasonId}`),
  seasons:          ()                         => get<Season[]>(`/api/seasons`),
  season:           (id: number)               => get<Season>(`/api/seasons/${id}`),
  // Analytics
  fullProfile:      (playerId: number)         => get<FullProfile>(`/api/player/${playerId}/full-profile`),
  trends:           (playerId: number, seasonId?: number) => get<{ player_id: number; trends: TrendPoint[] }>(`/api/player/${playerId}/trends${seasonId ? `?season_id=${seasonId}` : ''}`),
  h2h:              (p1: number, p2: number)   => get<H2HData>(`/api/player/${p1}/h2h/${p2}`),
  ratings:          ()                         => get<RatingEntry[]>(`/api/ratings`),
  ratingHistory:    (playerId: number)         => get<RatingHistoryPoint[]>(`/api/player/${playerId}/rating-history`),
}
