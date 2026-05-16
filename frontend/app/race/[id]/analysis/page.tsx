"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { useEffect, useMemo, useState } from "react"
import { RaceNav } from "@/components/RaceNav"
import { formatLapTime } from "@/lib/utils"
import { apiFetch } from "@/lib/api-client"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface LapData {
  lap: number
  time_ms: number
  s1_ms: number
  s2_ms: number
  s3_ms: number
  valid: boolean
}

interface Driver {
  vehicle_index: number
  driver_name: string
  team_name: string
  team_color: string
  is_human: boolean
  position: number | null
  grid_position: number | null
  best_lap_ms: number | null
  theoretical_best_ms: number | null
  best_sectors: { s1: number | null; s2: number | null; s3: number | null }
  tyre_stints: { compound: string; laps: number; end_lap?: number }[]
  num_pit_stops: number
  result_status: number
  points: number
  laps: LapData[]
}

interface Analysis {
  race_id: number
  track_name: string
  total_laps: number | null
  weather_start: number | null
  weather_end: number | null
  drivers: Driver[]
}

interface BrakingZone {
  distance: number
  distance_end: number
  braking_distance: number
  peak_brake: number
  entry_speed: number
  exit_speed: number
  min_speed: number
  trail_braking: boolean
}

interface BrakingDriver {
  vehicle_index: number
  driver_name: string
  team_color: string
  lap_number: number
  lap_time_ms: number
  zones: BrakingZone[]
}

interface ThrottleDriver {
  vehicle_index: number
  driver_name: string
  team_color: string
  lap_time_ms: number
  full_throttle_pct: number
  zero_throttle_pct: number
  partial_throttle_pct: number
  coasting_pct: number
  smoothness: number
  drs_pct: number
  max_speed: number
  avg_speed: number
}

interface WeatherCorrelation {
  weather_changes: { lap: number; weather_id: number; label: string }[]
  driver_impacts: {
    driver_name: string
    team_color: string
    is_human: boolean
    avg_pace_dry_ms: number | null
    avg_pace_wet_ms: number | null
    consistency_dry: number | null
    consistency_wet: number | null
    pace_delta_pct: number | null
    first_half_avg_ms: number | null
    second_half_avg_ms: number | null
  }[]
}

interface RaceInfo {
  id: number
  season_id: number
  track_name: string
  round: number
}

function getWeatherLabel(weatherId: number | null) {
  if (weatherId === null || weatherId === undefined) {
    return "Неизвестно"
  }
  return `Состояние ${weatherId}`
}

export default function RaceAnalysisPage() {
  const params = useParams<{ id: string }>()
  const raceId = Number(params.id)
  const { data: session } = useSession()
  const userId = session?.user?.id ? Number(session.user.id) : undefined

  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [raceInfo, setRaceInfo] = useState<RaceInfo | null>(null)
  const [braking, setBraking] = useState<BrakingDriver[]>([])
  const [throttle, setThrottle] = useState<ThrottleDriver[]>([])
  const [weather, setWeather] = useState<WeatherCorrelation | null>(null)
  const [loading, setLoading] = useState(true)
  const [debrief, setDebrief] = useState<string | null>(null)
  const [debriefLoading, setDebriefLoading] = useState(false)

  useEffect(() => {
    let active = true

    Promise.all([
      fetch(`${API}/api/race/${raceId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/telemetry/race-analysis/${raceId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/telemetry/braking-analysis/${raceId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/telemetry/throttle-analysis/${raceId}`).then((response) => (response.ok ? response.json() : null)),
      fetch(`${API}/api/telemetry/weather-correlation/${raceId}`).then((response) => (response.ok ? response.json() : null)),
    ])
      .then(([nextRaceInfo, nextAnalysis, nextBraking, nextThrottle, nextWeather]) => {
        if (!active) {
          return
        }
        setRaceInfo(nextRaceInfo)
        setAnalysis(nextAnalysis)
        setBraking(nextBraking?.drivers ?? [])
        setThrottle(nextThrottle?.drivers ?? [])
        setWeather(nextWeather)
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [raceId])

  async function requestDebrief() {
    if (!userId || debriefLoading) {
      return
    }

    setDebriefLoading(true)
    try {
      const response = await apiFetch(`/api/telemetry/race-analysis/${raceId}/debrief`, {
        method: "POST",
        body: JSON.stringify({ question: "Подготовь структурированный дебриф гонки: сильные стороны, слабые стороны и следующие шаги." }),
      })
      const payload = await response.json()
      setDebrief(payload.debrief ?? "Дебриф не был получен.")
    } catch {
      setDebrief("Сервис AI-дебрифа сейчас недоступен.")
    } finally {
      setDebriefLoading(false)
    }
  }

  const rankedDrivers = useMemo(
    () => [...(analysis?.drivers ?? [])].sort((a, b) => (a.position ?? 999) - (b.position ?? 999)),
    [analysis?.drivers],
  )
  const humanDrivers = useMemo(() => rankedDrivers.filter((driver) => driver.is_human), [rankedDrivers])
  const winner = rankedDrivers[0] ?? null
  const fastestDriver = useMemo(
    () =>
      [...rankedDrivers]
        .filter((driver) => driver.best_lap_ms)
        .sort((a, b) => (a.best_lap_ms ?? Number.POSITIVE_INFINITY) - (b.best_lap_ms ?? Number.POSITIVE_INFINITY))[0] ?? null,
    [rankedDrivers],
  )
  const averageStops = humanDrivers.length > 0 ? (humanDrivers.reduce((total, driver) => total + driver.num_pit_stops, 0) / humanDrivers.length).toFixed(1) : "0.0"
  const weatherSummary = weather?.weather_changes?.length
    ? weather.weather_changes.map((change) => `L${change.lap} ${change.label}`).join(" - ")
    : `${getWeatherLabel(analysis?.weather_start ?? null)} до ${getWeatherLabel(analysis?.weather_end ?? null)}`

  if (loading) {
    return <div className="py-20 text-center text-sm text-muted">Загрузка анализа гонки...</div>
  }

  if (!analysis || !raceInfo) {
    return <div className="py-20 text-center text-sm text-muted">Анализ гонки для этого события пока недоступен.</div>
  }

  return (
    <div className="page-stack">
      <RaceNav raceId={raceInfo.id} seasonId={raceInfo.season_id} trackName={raceInfo.track_name} round={raceInfo.round} />

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Анализ гонки</p>
            <h1 className="page-title">Дебриф по {analysis.track_name}, который начинается с контекста, а не с сырых инженерных графиков.</h1>
            <p className="page-copy">
              Это основная точка входа в разбор гонки. Сначала она показывает исход, стратегию и ключевые технические
              маркеры, а уже потом уводит в сравнение кругов, повтор и сырую телеметрию, когда действительно нужен
              более глубокий слой.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/compare/${raceId}`} className="ui-button-secondary">
                Сравнить круги
              </Link>
              <Link href={`/telemetry/${raceId}`} className="ui-button-tertiary">
                Сырая телеметрия
              </Link>
              <Link href={`/race/${raceId}/replay`} className="ui-button-tertiary">
                Повтор
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Сводка гонки</p>
            <p className="mt-3 text-2xl font-semibold text-text">{winner?.driver_name ?? "Нет классифицированного победителя"}</p>
            <p className="mt-2 text-sm text-muted">
              {winner ? `${winner.team_name} - ${winner.points} очков` : "Ждем классифицированный результат"}
            </p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Победитель</p>
          <p className="stat-value">{winner?.driver_name ?? "Ожидается"}</p>
          <p className="mt-2 text-sm text-muted">{winner?.team_name ?? "Победитель не зафиксирован"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Быстрейший круг</p>
          <p className="stat-value mono-data">{formatLapTime(fastestDriver?.best_lap_ms ?? null)}</p>
          <p className="mt-2 text-sm text-muted">{fastestDriver?.driver_name ?? "Нет данных по кругам"}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Среднее число пит-стопов</p>
          <p className="stat-value mono-data">{averageStops}</p>
          <p className="mt-2 text-sm text-muted">Только пилоты-люди</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Таймлайн погоды</p>
          <p className="stat-value">{weather?.weather_changes?.length ? `${weather.weather_changes.length} изменений` : "Стабильно"}</p>
          <p className="mt-2 text-sm text-muted">{weatherSummary}</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_320px]">
        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Навигация по анализу</p>
            <h2 className="mt-2 section-title">Выберите следующий слой исходя из того, какой вопрос вы решаете.</h2>
          </div>
          <div className="grid gap-4 p-6 md:grid-cols-3">
            <div className="rounded-[16px] border border-border bg-surfaceAlt/70 p-4">
              <p className="text-sm font-semibold text-text">Исход</p>
              <p className="mt-3 text-sm leading-6 text-muted">Используйте эту страницу, чтобы понять порядок, качество исполнения и паттерны пит-стопов.</p>
            </div>
            <div className="rounded-[16px] border border-border bg-surfaceAlt/70 p-4">
              <p className="text-sm font-semibold text-text">Пилот к пилоту</p>
              <p className="mt-3 text-sm leading-6 text-muted">Открывайте сравнение кругов, когда нужен прямой дельта-разбор лучших попыток двух конкретных пилотов.</p>
            </div>
            <div className="rounded-[16px] border border-border bg-surfaceAlt/70 p-4">
              <p className="text-sm font-semibold text-text">Пространственный разбор</p>
              <p className="mt-3 text-sm leading-6 text-muted">Открывайте повтор, чтобы увидеть траектории лучших кругов по трассе перед переходом к сырым сэмплам.</p>
            </div>
          </div>
        </div>

        <div className="surface-panel p-5">
          <p className="eyebrow">Почему это важно</p>
          <p className="mt-4 text-sm leading-7 text-muted">
            Глубокий анализ по-прежнему доступен, но стартовый экран теперь сначала объясняет, что произошло, почему это
            скорее всего произошло и куда идти дальше, вместо мгновенного провала в инженерные контролы.
          </p>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Исполнение пилотов</p>
          <h2 className="mt-2 section-title">Результат, потолок темпа и исполнение в одной таблице.</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[920px]">
            <thead>
              <tr>
                <th>Поз</th>
                <th>Пилот</th>
                <th className="text-right">Дельта грида</th>
                <th className="text-right">Лучший круг</th>
                <th className="text-right">Теор. отрыв</th>
                <th className="text-right">Питы</th>
                <th className="text-right">Очки</th>
              </tr>
            </thead>
            <tbody>
              {rankedDrivers.map((driver) => {
                const gridDelta = driver.position !== null && driver.grid_position !== null ? driver.grid_position - driver.position : null
                const theoreticalGap =
                  driver.best_lap_ms && driver.theoretical_best_ms ? driver.best_lap_ms - driver.theoretical_best_ms : null

                return (
                  <tr key={driver.vehicle_index} className={driver.is_human ? "player-row" : undefined}>
                    <td className="mono-data text-muted">{driver.position ? `P${driver.position}` : "--"}</td>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-1 rounded-full" style={{ backgroundColor: driver.team_color }} />
                        <div>
                          <p className="font-medium text-text">{driver.driver_name}</p>
                          <p className="mt-1 text-xs text-muted">{driver.team_name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="text-right mono-data text-muted">
                      {gridDelta === null ? "--" : gridDelta > 0 ? `+${gridDelta}` : `${gridDelta}`}
                    </td>
                    <td className="text-right mono-data text-text">{formatLapTime(driver.best_lap_ms)}</td>
                    <td className="text-right mono-data text-muted">{theoreticalGap !== null ? formatLapTime(theoreticalGap) : "--"}</td>
                    <td className="text-right mono-data text-muted">{driver.num_pit_stops}</td>
                    <td className="text-right mono-data font-semibold text-text">{driver.points}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border px-6 py-4">
          <p className="insight-line">Эта таблица совмещает финишный порядок и потолок темпа, поэтому слабый результат из-за проблем исполнения виден сразу.</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Профиль газа</p>
            <h2 className="mt-2 section-title">Маркеры смелости и скорости.</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[640px]">
              <thead>
                <tr>
                  <th>Пилот</th>
                  <th className="text-right">Полный газ</th>
                  <th className="text-right">Катание</th>
                  <th className="text-right">Макс. скорость</th>
                  <th className="text-right">Плавность</th>
                </tr>
              </thead>
              <tbody>
                {throttle.map((driver) => (
                  <tr key={driver.vehicle_index}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-1 rounded-full" style={{ backgroundColor: driver.team_color }} />
                        <span className="font-medium text-text">{driver.driver_name}</span>
                      </div>
                    </td>
                    <td className="text-right mono-data text-muted">{driver.full_throttle_pct.toFixed(1)}%</td>
                    <td className="text-right mono-data text-muted">{driver.coasting_pct.toFixed(1)}%</td>
                    <td className="text-right mono-data text-text">{driver.max_speed.toFixed(0)} km/h</td>
                    <td className="text-right mono-data text-muted">{driver.smoothness.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border px-6 py-4">
          <p className="insight-line">Анализ газа показывает смелость и скорость на прямиках, не заставляя сразу идти в график по каждому сэмплу.</p>
          </div>
        </div>

        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Профиль торможений</p>
            <h2 className="mt-2 section-title">Насколько агрессивно круг замедляется и разворачивается.</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[640px]">
              <thead>
                <tr>
                  <th>Пилот</th>
                  <th className="text-right">Зоны</th>
                  <th className="text-right">Сред. торможение</th>
                  <th className="text-right">Сред. мин. скорость</th>
                  <th className="text-right">Trail-зоны</th>
                </tr>
              </thead>
              <tbody>
                {braking.map((driver) => {
                  const avgPeakBrake = driver.zones.length > 0 ? driver.zones.reduce((total, zone) => total + zone.peak_brake, 0) / driver.zones.length : 0
                  const avgMinSpeed = driver.zones.length > 0 ? driver.zones.reduce((total, zone) => total + zone.min_speed, 0) / driver.zones.length : 0
                  const trailZones = driver.zones.filter((zone) => zone.trail_braking).length

                  return (
                    <tr key={driver.vehicle_index}>
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-1 rounded-full" style={{ backgroundColor: driver.team_color }} />
                          <span className="font-medium text-text">{driver.driver_name}</span>
                        </div>
                      </td>
                      <td className="text-right mono-data text-muted">{driver.zones.length}</td>
                      <td className="text-right mono-data text-muted">{avgPeakBrake.toFixed(0)}%</td>
                      <td className="text-right mono-data text-text">{avgMinSpeed.toFixed(0)} km/h</td>
                      <td className="text-right mono-data text-muted">{trailZones}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border px-6 py-4">
          <p className="insight-line">Маркеры торможения чисто показывают различия техники еще до того, как вы решите идти в поворотный разбор.</p>
          </div>
        </div>
      </section>

      {weather?.driver_impacts?.length ? (
        <section className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Влияние погоды</p>
            <h2 className="mt-2 section-title">Как менялся темп вместе с условиями.</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[860px]">
              <thead>
                <tr>
                  <th>Пилот</th>
                  <th className="text-right">Сухой темп</th>
                  <th className="text-right">Мокрый темп</th>
                  <th className="text-right">Дельта темпа</th>
                  <th className="text-right">Первая половина</th>
                  <th className="text-right">Вторая половина</th>
                </tr>
              </thead>
              <tbody>
                {weather.driver_impacts.map((driver) => (
                  <tr key={driver.driver_name}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-1 rounded-full" style={{ backgroundColor: driver.team_color }} />
                        <span className="font-medium text-text">{driver.driver_name}</span>
                      </div>
                    </td>
                    <td className="text-right mono-data text-muted">{formatLapTime(driver.avg_pace_dry_ms)}</td>
                    <td className="text-right mono-data text-muted">{formatLapTime(driver.avg_pace_wet_ms)}</td>
                    <td className="text-right mono-data text-text">{driver.pace_delta_pct !== null ? `${driver.pace_delta_pct.toFixed(1)}%` : "--"}</td>
                    <td className="text-right mono-data text-muted">{formatLapTime(driver.first_half_avg_ms)}</td>
                    <td className="text-right mono-data text-muted">{formatLapTime(driver.second_half_avg_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="surface-panel p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="eyebrow">AI-дебриф</p>
            <h2 className="mt-2 section-title">Запросите структурированный разбор гонки.</h2>
            <p className="mt-4 max-w-[58ch] text-sm leading-7 text-muted">
              AI-дебриф идет после фактической сводки. Это делает страницу надежной: сначала наблюдаемое состояние гонки,
              потом интерпретирующий слой.
            </p>
          </div>
          {userId ? (
            <button onClick={requestDebrief} disabled={debriefLoading} className="ui-button-secondary">
              {debriefLoading ? "Генерируем дебриф..." : "Сгенерировать дебриф"}
            </button>
          ) : (
            <Link href="/login" className="ui-button-tertiary">
              Войти для дебрифа
            </Link>
          )}
        </div>

        {debrief ? (
          <div className="mt-6 rounded-[16px] border border-border bg-surfaceAlt/70 p-5 text-sm leading-7 text-text whitespace-pre-wrap">
            {debrief}
          </div>
        ) : null}
      </section>
    </div>
  )
}
