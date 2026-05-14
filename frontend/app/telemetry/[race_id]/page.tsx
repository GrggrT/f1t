"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import TrackMap, { SpeedLegend } from "@/components/TrackMap"
import { RaceNav } from "@/components/RaceNav"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

type ColorMetric = "speed" | "throttle" | "brake" | "gear" | "ers" | "steer" | "tyre_wear"

interface LapEntry {
  lap: number
  lap_ms: number | null
}

interface DriverInfo {
  vehicle_index: number
  driver_name: string
  team_color: string
  is_human: boolean
  laps: LapEntry[]
}

interface Sample {
  t: number
  x: number
  z: number
  spd: number
  thr: number
  brk: number
  gear: number
  drs: number
  dist: number
  ers?: number
  str?: number
  fuel?: number
  tw?: number
}

interface LapData {
  vehicle_index: number
  lap_number: number
  lap_time_ms: number | null
  samples: Sample[]
}

interface RaceInfo {
  id: number
  season_id: number
  track_name: string
  round: number
}

function fmtLap(ms: number | null) {
  if (!ms) return "--"
  const totalSeconds = ms / 1000
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = (totalSeconds % 60).toFixed(3)
  return `${minutes}:${seconds.padStart(6, "0")}`
}

const METRIC_LABELS: Record<ColorMetric, string> = {
  speed: "Скорость",
  throttle: "Газ",
  brake: "Тормоз",
  gear: "Передача",
  ers: "ERS",
  steer: "Руль",
  tyre_wear: "Износ шин",
}

export default function TelemetryPage() {
  const { race_id } = useParams<{ race_id: string }>()
  const [raceInfo, setRaceInfo] = useState<RaceInfo | null>(null)
  const [drivers, setDrivers] = useState<DriverInfo[]>([])
  const [selectedDriver, setSelectedDriver] = useState<number | null>(null)
  const [selectedLap, setSelectedLap] = useState<number | null>(null)
  const [lapData, setLapData] = useState<LapData | null>(null)
  const [metric, setMetric] = useState<ColorMetric>("speed")
  const [loadingLap, setLoadingLap] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/race/${race_id}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setRaceInfo)
      .catch(() => {})

    fetch(`${API}/api/telemetry/${race_id}`)
      .then((response) => response.json())
      .then((payload: DriverInfo[]) => {
        setDrivers(payload)

        const defaultDriver = payload.find((driver) => driver.is_human) ?? payload[0]
        if (!defaultDriver) {
          return
        }

        setSelectedDriver(defaultDriver.vehicle_index)

        const bestLap = [...defaultDriver.laps]
          .filter((lap) => lap.lap_ms)
          .sort((a, b) => (a.lap_ms ?? 0) - (b.lap_ms ?? 0))[0]

        if (bestLap) {
          setSelectedLap(bestLap.lap)
        }
      })
      .catch(() => {})
  }, [race_id])

  const loadLap = useCallback(
    async (vehicleIndex: number, lap: number) => {
      setLoadingLap(true)
      try {
        const response = await fetch(`${API}/api/telemetry/${race_id}/${vehicleIndex}/${lap}`)
        if (response.ok) {
          setLapData(await response.json())
        }
      } finally {
        setLoadingLap(false)
      }
    },
    [race_id],
  )

  useEffect(() => {
    if (selectedDriver !== null && selectedLap !== null) {
      loadLap(selectedDriver, selectedLap)
    }
  }, [loadLap, selectedDriver, selectedLap])

  const activeDriver = drivers.find((driver) => driver.vehicle_index === selectedDriver) ?? null

  return (
    <div className="page-stack">
      {raceInfo ? <RaceNav raceId={raceInfo.id} seasonId={raceInfo.season_id} trackName={raceInfo.track_name} round={raceInfo.round} /> : null}

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Телеметрия</p>
            <h2 className="section-title">Состояние трассы круг за кругом с guided-entry.</h2>
            <p className="page-copy">
              Начните с пилота и лучшего круга, а потом переходите к метрике, которая объясняет темп. Телеметрия больше не
              выглядит как холодный инженерный экран без гоночного контекста.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/compare/${race_id}`} className="ui-button-secondary">
                Сравнить пилотов
              </Link>
              <Link href={`/race/${race_id}/analysis`} className="ui-button-tertiary">
                Анализ гонки
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Текущий выбор</p>
            <p className="mt-3 text-xl font-semibold text-text">{activeDriver?.driver_name ?? "Выберите пилота"}</p>
            <p className="mt-2 text-sm text-muted">
              {lapData ? `Круг ${lapData.lap_number} · ${fmtLap(lapData.lap_time_ms)}` : "Выберите круг, чтобы отрисовать карту трассы"}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[290px_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="surface-panel p-4">
            <p className="eyebrow">Пилот</p>
            <div className="mt-4 space-y-2">
              {drivers.map((driver) => (
                <button
                  key={driver.vehicle_index}
                  onClick={() => {
                    setSelectedDriver(driver.vehicle_index)
                    const bestLap = [...driver.laps]
                      .filter((lap) => lap.lap_ms)
                      .sort((a, b) => (a.lap_ms ?? 0) - (b.lap_ms ?? 0))[0]

                    if (bestLap) {
                      setSelectedLap(bestLap.lap)
                    }
                  }}
                  className={`flex w-full items-center gap-3 rounded-[12px] border px-3 py-3 text-left transition-colors ${
                    selectedDriver === driver.vehicle_index ? "border-borderStrong bg-surfaceAlt text-text" : "border-border bg-surface/60 text-muted hover:bg-surfaceAlt"
                  }`}
                >
                  <span className="h-3 w-3 rounded-full" style={{ background: driver.team_color }} />
                  <span className="flex-1">{driver.driver_name}</span>
                  {driver.is_human ? <span className="data-pill">Игрок</span> : null}
                </button>
              ))}
            </div>
          </div>

          <div className="surface-panel p-4">
            <p className="eyebrow">Круг</p>
            <div className="mt-4 max-h-[320px] space-y-2 overflow-y-auto">
              {activeDriver?.laps.map((lap) => (
                <button
                  key={lap.lap}
                  onClick={() => setSelectedLap(lap.lap)}
                  className={`flex w-full items-center justify-between rounded-[12px] border px-3 py-3 text-sm transition-colors ${
                    selectedLap === lap.lap ? "border-borderStrong bg-surfaceAlt text-text" : "border-border bg-surface/60 text-muted hover:bg-surfaceAlt"
                  }`}
                >
                  <span>Круг {lap.lap}</span>
                  <span className="mono-data">{fmtLap(lap.lap_ms)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="surface-panel p-4">
            <p className="eyebrow">Метрика</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {(Object.keys(METRIC_LABELS) as ColorMetric[]).map((entry) => (
                <button
                  key={entry}
                  onClick={() => setMetric(entry)}
                  className={`rounded-[12px] border px-3 py-2 text-xs uppercase tracking-[0.14em] transition-colors ${
                    metric === entry ? "border-borderStrong bg-surfaceAlt text-text" : "border-border bg-surface/60 text-muted hover:bg-surfaceAlt"
                  }`}
                >
                  {METRIC_LABELS[entry]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {loadingLap ? (
            <div className="surface-panel flex min-h-[520px] items-center justify-center text-sm text-muted">Загрузка телеметрии...</div>
          ) : lapData ? (
            <>
              <div className="surface-panel p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm font-medium text-text">{activeDriver?.driver_name}</p>
                  <span className="data-pill">Круг {lapData.lap_number}</span>
                  <span className="mono-data text-sm text-muted">{fmtLap(lapData.lap_time_ms)}</span>
                  <span className="ml-auto text-sm text-muted">{lapData.samples.length} samples</span>
                </div>
              </div>

              <div className="surface-panel overflow-hidden p-3">
                <TrackMap samples={lapData.samples} metric={metric} width={860} height={560} teamColor={activeDriver?.team_color} />
              </div>

              <div className="surface-panel p-5">
                <div className="flex flex-wrap items-center gap-4">
                  <span className="utility-kicker">Легенда</span>
                  {metric === "speed" ? <SpeedLegend /> : null}
                  {metric === "throttle" ? <span className="text-xs text-muted">Зеленый показывает нажатие газа.</span> : null}
                  {metric === "brake" ? <span className="text-xs text-muted">Красный показывает интенсивность торможения.</span> : null}
                  {metric === "gear" ? <span className="text-xs text-muted">Цвет сегмента показывает активную передачу.</span> : null}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="stat-card">
                  <p className="stat-label">Макс. скорость</p>
                  <p className="mt-2 mono-data text-lg font-semibold text-text">{Math.max(...lapData.samples.map((sample) => sample.spd))} km/h</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Средняя скорость</p>
                  <p className="mt-2 mono-data text-lg font-semibold text-text">
                    {Math.round(lapData.samples.reduce((sum, sample) => sum + sample.spd, 0) / lapData.samples.length)} km/h
                  </p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">DRS-сэмплы</p>
                  <p className="mt-2 mono-data text-lg font-semibold text-text">{lapData.samples.filter((sample) => sample.drs).length}</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Отрисованные точки</p>
                  <p className="mt-2 mono-data text-lg font-semibold text-text">{lapData.samples.length}</p>
                </div>
              </div>
            </>
          ) : (
            <div className="surface-panel flex min-h-[520px] items-center justify-center text-sm text-muted">
              Выберите пилота и круг, чтобы отрисовать телеметрию.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
