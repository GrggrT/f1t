"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import TrackMap from "@/components/TrackMap"
import { RaceNav } from "@/components/RaceNav"
import { formatLapTime } from "@/lib/utils"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

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

interface LapInfo {
  vehicle_index: number
  driver_name: string
  team_color: string
  lap_number: number
  lap_time_ms: number | null
  samples: Sample[]
}

interface CompareData {
  a: LapInfo
  b: LapInfo
}

interface DriverInfo {
  vehicle_index: number
  driver_name: string
  team_color: string
  is_human: boolean
}

interface RaceInfo {
  id: number
  season_id: number
  track_name: string
  round: number
}

function buildTelemetryStats(lap: LapInfo) {
  const samples = lap.samples
  const sampleCount = samples.length || 1
  const maxSpeed = Math.max(...samples.map((sample) => sample.spd), 0)
  const avgSpeed = samples.reduce((total, sample) => total + sample.spd, 0) / sampleCount
  const fullThrottlePct = (samples.filter((sample) => sample.thr >= 0.95).length / sampleCount) * 100
  const brakePct = (samples.filter((sample) => sample.brk > 0.05).length / sampleCount) * 100
  const drsPct = (samples.filter((sample) => sample.drs > 0).length / sampleCount) * 100
  const minSpeed = Math.min(...samples.map((sample) => sample.spd))
  const distance = Math.max(...samples.map((sample) => sample.dist), 0)

  return {
    maxSpeed,
    avgSpeed,
    fullThrottlePct,
    brakePct,
    drsPct,
    minSpeed: Number.isFinite(minSpeed) ? minSpeed : 0,
    distance,
  }
}

function formatDelta(a: number | null, b: number | null) {
  if (!a || !b) {
    return "--"
  }
  const seconds = (a - b) / 1000
  return `${seconds > 0 ? "+" : ""}${seconds.toFixed(3)}s`
}

export default function ComparePage() {
  const { race_id } = useParams<{ race_id: string }>()

  const [raceInfo, setRaceInfo] = useState<RaceInfo | null>(null)
  const [drivers, setDrivers] = useState<DriverInfo[]>([])
  const [selectedA, setSelectedA] = useState<number | null>(null)
  const [selectedB, setSelectedB] = useState<number | null>(null)
  const [data, setData] = useState<CompareData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/race/${race_id}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setRaceInfo)
      .catch(() => {})

    fetch(`${API}/api/telemetry/${race_id}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((payload: DriverInfo[]) => {
        setDrivers(payload)
        if (payload.length >= 2) {
          setSelectedA(payload[0].vehicle_index)
          setSelectedB(payload[1].vehicle_index)
        } else if (payload.length === 1) {
          setSelectedA(payload[0].vehicle_index)
          setSelectedB(payload[0].vehicle_index)
        }
      })
      .catch(() => {})
  }, [race_id])

  useEffect(() => {
    if (selectedA === null || selectedB === null || selectedA === selectedB) {
      return
    }

    setLoading(true)
    fetch(`${API}/api/telemetry/${race_id}/compare?a=${selectedA}&b=${selectedB}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setData)
      .finally(() => setLoading(false))
  }, [race_id, selectedA, selectedB])

  const statsA = useMemo(() => (data ? buildTelemetryStats(data.a) : null), [data])
  const statsB = useMemo(() => (data ? buildTelemetryStats(data.b) : null), [data])
  const lapDelta = data ? formatDelta(data.a.lap_time_ms, data.b.lap_time_ms) : "--"
  const fasterDriver =
    data && data.a.lap_time_ms && data.b.lap_time_ms
      ? data.a.lap_time_ms <= data.b.lap_time_ms
        ? data.a.driver_name
        : data.b.driver_name
      : null

  return (
    <div className="page-stack">
      {raceInfo ? <RaceNav raceId={raceInfo.id} seasonId={raceInfo.season_id} trackName={raceInfo.track_name} round={raceInfo.round} /> : null}

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Сравнение кругов</p>
            <h1 className="page-title">Прямое сравнение лучших кругов с контекстом, готовым к решению.</h1>
            <p className="page-copy">
              Сравнение это ветка анализа пилот-к-пилоту. Выберите двух пилотов, поймите главную дельту, а потом используйте
              карты трассы и телеметрические маркеры, чтобы увидеть, откуда скорее всего идет разница в темпе.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/race/${race_id}/analysis`} className="ui-button-secondary">
                Назад к анализу
              </Link>
              <Link href={`/telemetry/${race_id}`} className="ui-button-tertiary">
                Сырая телеметрия
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Состояние сравнения</p>
            <p className="mt-3 text-2xl font-semibold text-text">{fasterDriver ?? "Выберите двух пилотов"}</p>
            <p className="mt-2 text-sm text-muted">{data ? `Дельта круга ${lapDelta}` : "Ждем валидные данные для сравнения"}</p>
          </div>
        </div>
      </section>

      {drivers.length < 2 ? (
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Недостаточно телеметрии</p>
            <h2 className="mt-3 section-title">Для режима сравнения нужны как минимум два пилота.</h2>
          <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
            Когда телеметрия появится хотя бы у двух пилотов, этот маршрут станет каноничной поверхностью side-by-side сравнения кругов.
          </p>
        </section>
      ) : (
        <>
          <section className="grid gap-6 xl:grid-cols-2">
            {[
              { label: "Пилот A", value: selectedA, setValue: setSelectedA, lap: data?.a },
              { label: "Пилот B", value: selectedB, setValue: setSelectedB, lap: data?.b },
            ].map((item) => (
              <div key={item.label} className="surface-panel p-6">
                <p className="eyebrow">{item.label}</p>
                <div className="mt-4 space-y-4">
                  <select
                    value={item.value ?? ""}
                    onChange={(event) => item.setValue(Number(event.target.value))}
                    className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                  >
                    {drivers.map((driver) => (
                      <option key={driver.vehicle_index} value={driver.vehicle_index}>
                        {driver.driver_name}
                      </option>
                    ))}
                  </select>
                  <div className="rounded-[16px] border border-border bg-surfaceAlt/70 p-4">
                    <div className="flex items-center gap-3">
                      {item.lap ? <span className="h-3 w-3 rounded-full" style={{ backgroundColor: item.lap.team_color }} /> : null}
                      <p className="font-medium text-text">{item.lap?.driver_name ?? "Ждем данные"}</p>
                    </div>
                    <p className="mt-3 mono-data text-2xl text-text">{formatLapTime(item.lap?.lap_time_ms ?? null)}</p>
                    <p className="mt-2 text-sm text-muted">{item.lap ? `Лучший круг - круг ${item.lap.lap_number}` : "Выберите валидную пару пилотов"}</p>
                  </div>
                </div>
              </div>
            ))}
          </section>

          <section className="summary-grid">
            <div className="stat-card">
              <p className="stat-label">Дельта круга</p>
              <p className="stat-value mono-data">{lapDelta}</p>
              <p className="mt-2 text-sm text-muted">Пилот A относительно пилота B</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Более быстрый круг</p>
              <p className="stat-value">{fasterDriver ?? "--"}</p>
              <p className="mt-2 text-sm text-muted">Победитель по лучшему кругу в текущей паре</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Дельта максимальной скорости</p>
              <p className="stat-value mono-data">
                {statsA && statsB ? `${(statsA.maxSpeed - statsB.maxSpeed).toFixed(0)} km/h` : "--"}
              </p>
              <p className="mt-2 text-sm text-muted">Пилот A минус пилот B</p>
            </div>
            <div className="stat-card">
              <p className="stat-label">Пройденная дистанция</p>
              <p className="stat-value mono-data">{statsA ? `${Math.round(statsA.distance)} m` : "--"}</p>
              <p className="mt-2 text-sm text-muted">Длина телеметрического трека лучшего круга</p>
            </div>
          </section>

          {loading ? <div className="py-12 text-center text-sm text-muted">Загрузка телеметрии сравнения...</div> : null}

          {data ? (
            <>
              <section className="grid gap-6 xl:grid-cols-2">
                <div className="surface-panel overflow-hidden">
                  <div className="border-b border-border px-6 py-5">
                    <p className="eyebrow">Карта пилота A</p>
                    <h2 className="mt-2 section-title">{data.a.driver_name}</h2>
                  </div>
                  <div className="p-5">
                    <TrackMap samples={data.a.samples} metric="speed" width={640} height={420} teamColor={data.a.team_color} />
                  </div>
                </div>

                <div className="surface-panel overflow-hidden">
                  <div className="border-b border-border px-6 py-5">
                    <p className="eyebrow">Карта пилота B</p>
                    <h2 className="mt-2 section-title">{data.b.driver_name}</h2>
                  </div>
                  <div className="p-5">
                    <TrackMap samples={data.b.samples} metric="speed" width={640} height={420} teamColor={data.b.team_color} />
                  </div>
                </div>
              </section>

              <section className="surface-panel overflow-hidden">
                <div className="border-b border-border px-6 py-5">
                  <p className="eyebrow">Телеметрические маркеры</p>
                  <h2 className="mt-2 section-title">Скорость, газ, торможение и DRS без перегруза графиками.</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="data-table min-w-[840px]">
                    <thead>
                      <tr>
                        <th>Метрика</th>
                        <th className="text-right">{data.a.driver_name}</th>
                        <th className="text-right">{data.b.driver_name}</th>
                        <th className="text-right">Дельта</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Время круга</td>
                        <td className="text-right mono-data text-text">{formatLapTime(data.a.lap_time_ms)}</td>
                        <td className="text-right mono-data text-text">{formatLapTime(data.b.lap_time_ms)}</td>
                        <td className="text-right mono-data text-muted">{lapDelta}</td>
                      </tr>
                      <tr>
                        <td>Макс. скорость</td>
                        <td className="text-right mono-data text-text">{statsA?.maxSpeed.toFixed(0)} km/h</td>
                        <td className="text-right mono-data text-text">{statsB?.maxSpeed.toFixed(0)} km/h</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.maxSpeed - statsB.maxSpeed).toFixed(0)} km/h` : "--"}
                        </td>
                      </tr>
                      <tr>
                        <td>Средняя скорость</td>
                        <td className="text-right mono-data text-text">{statsA?.avgSpeed.toFixed(1)} km/h</td>
                        <td className="text-right mono-data text-text">{statsB?.avgSpeed.toFixed(1)} km/h</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.avgSpeed - statsB.avgSpeed).toFixed(1)} km/h` : "--"}
                        </td>
                      </tr>
                      <tr>
                        <td>Полный газ</td>
                        <td className="text-right mono-data text-text">{statsA?.fullThrottlePct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-text">{statsB?.fullThrottlePct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.fullThrottlePct - statsB.fullThrottlePct).toFixed(1)}%` : "--"}
                        </td>
                      </tr>
                      <tr>
                        <td>Доля торможения</td>
                        <td className="text-right mono-data text-text">{statsA?.brakePct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-text">{statsB?.brakePct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.brakePct - statsB.brakePct).toFixed(1)}%` : "--"}
                        </td>
                      </tr>
                      <tr>
                        <td>Доля DRS</td>
                        <td className="text-right mono-data text-text">{statsA?.drsPct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-text">{statsB?.drsPct.toFixed(1)}%</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.drsPct - statsB.drsPct).toFixed(1)}%` : "--"}
                        </td>
                      </tr>
                      <tr>
                        <td>Минимальная скорость</td>
                        <td className="text-right mono-data text-text">{statsA?.minSpeed.toFixed(0)} km/h</td>
                        <td className="text-right mono-data text-text">{statsB?.minSpeed.toFixed(0)} km/h</td>
                        <td className="text-right mono-data text-muted">
                          {statsA && statsB ? `${(statsA.minSpeed - statsB.minSpeed).toFixed(0)} km/h` : "--"}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="border-t border-border px-6 py-4">
                  <p className="insight-line">
            Теперь сравнение начинается с читаемой телеметрической сводки. Трассировочный контур по-прежнему доступен,
                    но только после того, как понятны главная дельта круга и ключевые технические маркеры.
                  </p>
                </div>
              </section>
            </>
          ) : null}
        </>
      )}
    </div>
  )
}
