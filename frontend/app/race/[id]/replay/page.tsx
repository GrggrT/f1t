"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useEffect, useRef, useState } from "react"
import { RaceNav } from "@/components/RaceNav"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface DriverInfo {
  vehicle_index: number
  driver_name: string
  team_color: string
  is_human: boolean
  position: number | null
}

interface RaceInfo {
  id: number
  season_id: number
  track_name: string
  round: number
}

interface Sample {
  x: number
  z: number
  spd: number
}

export default function ReplayPage() {
  const params = useParams<{ id: string }>()
  const raceId = Number(params.id)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const frameRef = useRef(0)
  const lastTimeRef = useRef(0)
  const speedRef = useRef(1)

  const [drivers, setDrivers] = useState<DriverInfo[]>([])
  const [raceInfo, setRaceInfo] = useState<RaceInfo | null>(null)
  const [telemetryData, setTelemetryData] = useState<Map<number, Sample[]>>(new Map())
  const [loading, setLoading] = useState(true)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [maxFrames, setMaxFrames] = useState(0)
  const [trackBounds, setTrackBounds] = useState({ minX: 0, maxX: 0, minZ: 0, maxZ: 0 })
  const [currentFrame, setCurrentFrame] = useState(0)

  speedRef.current = speed

  useEffect(() => {
    fetch(`${API}/api/race/${raceId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setRaceInfo)
      .catch(() => {})

    async function load() {
      try {
        const analysisResponse = await fetch(`${API}/api/telemetry/race-analysis/${raceId}`)
        if (!analysisResponse.ok) {
          return
        }

        const analysis = await analysisResponse.json()
        const humanDrivers = analysis.drivers.filter((driver: any) => driver.is_human)

        setDrivers(
          humanDrivers.map((driver: any) => ({
            vehicle_index: driver.vehicle_index,
            driver_name: driver.driver_name,
            team_color: driver.team_color,
            is_human: true,
            position: driver.position,
          })),
        )

        const nextTelemetry = new Map<number, Sample[]>()
        let globalMinX = Infinity
        let globalMaxX = -Infinity
        let globalMinZ = Infinity
        let globalMaxZ = -Infinity
        let nextMaxFrames = 0

        for (const driver of humanDrivers) {
          try {
            const response = await fetch(`${API}/api/telemetry/${raceId}/${driver.vehicle_index}/best`)
            if (!response.ok) {
              continue
            }

            const payload = await response.json()
            if (!payload.samples?.length) {
              continue
            }

            nextTelemetry.set(driver.vehicle_index, payload.samples)
            nextMaxFrames = Math.max(nextMaxFrames, payload.samples.length)

            for (const sample of payload.samples) {
              if (sample.x < globalMinX) globalMinX = sample.x
              if (sample.x > globalMaxX) globalMaxX = sample.x
              if (sample.z < globalMinZ) globalMinZ = sample.z
              if (sample.z > globalMaxZ) globalMaxZ = sample.z
            }
          } catch {
            // Ignore missing telemetry for individual drivers.
          }
        }

        setTelemetryData(nextTelemetry)
        setMaxFrames(nextMaxFrames)
        setTrackBounds({ minX: globalMinX, maxX: globalMaxX, minZ: globalMinZ, maxZ: globalMaxZ })
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [raceId])

  const draw = useCallback(
    (frame: number) => {
      const canvas = canvasRef.current
      if (!canvas) {
        return
      }

      const context = canvas.getContext("2d")
      if (!context) {
        return
      }

      const width = canvas.width
      const height = canvas.height
      const padding = 40
      const { minX, maxX, minZ, maxZ } = trackBounds

      const rangeX = maxX - minX || 1
      const rangeZ = maxZ - minZ || 1
      const scale = Math.min((width - padding * 2) / rangeX, (height - padding * 2) / rangeZ)
      const offsetX = (width - rangeX * scale) / 2
      const offsetZ = (height - rangeZ * scale) / 2

      const toCanvasX = (x: number) => offsetX + (x - minX) * scale
      const toCanvasZ = (z: number) => offsetZ + (z - minZ) * scale

      context.fillStyle = "#080c10"
      context.fillRect(0, 0, width, height)

      const firstTrace = telemetryData.values().next().value
      if (firstTrace) {
        context.beginPath()
        context.strokeStyle = "rgba(255,255,255,0.1)"
        context.lineWidth = 12
        context.lineCap = "round"
        context.lineJoin = "round"
        firstTrace.forEach((sample: Sample, index: number) => {
          const x = toCanvasX(sample.x)
          const z = toCanvasZ(sample.z)
          if (index === 0) {
            context.moveTo(x, z)
          } else {
            context.lineTo(x, z)
          }
        })
        context.stroke()
      }

      for (const driver of drivers) {
        const samples = telemetryData.get(driver.vehicle_index)
        if (!samples?.length) {
          continue
        }

        const index = Math.min(frame, samples.length - 1)
        const sample = samples[index]
        const x = toCanvasX(sample.x)
        const z = toCanvasZ(sample.z)

        context.beginPath()
        context.strokeStyle = `${driver.team_color}60`
        context.lineWidth = 3
        const trailStart = Math.max(0, index - 20)
        for (let sampleIndex = trailStart; sampleIndex <= index; sampleIndex += 1) {
          const trailX = toCanvasX(samples[sampleIndex].x)
          const trailZ = toCanvasZ(samples[sampleIndex].z)
          if (sampleIndex === trailStart) {
            context.moveTo(trailX, trailZ)
          } else {
            context.lineTo(trailX, trailZ)
          }
        }
        context.stroke()

        context.beginPath()
        context.fillStyle = driver.team_color
        context.arc(x, z, 6, 0, Math.PI * 2)
        context.fill()
        context.strokeStyle = "#ffffff"
        context.lineWidth = 1.5
        context.stroke()

        context.fillStyle = driver.team_color
        context.font = "bold 10px IBM Plex Sans, sans-serif"
        context.textAlign = "left"
        context.fillText(driver.driver_name.split(" ").pop()?.slice(0, 6) || driver.driver_name.slice(0, 6), x + 10, z + 4)

        context.fillStyle = "#7e8997"
        context.font = "9px IBM Plex Sans, sans-serif"
        context.fillText(`${sample.spd} km/h`, x + 10, z + 15)
      }

      context.fillStyle = "#7e8997"
      context.font = "11px IBM Plex Mono, monospace"
      context.textAlign = "left"
      context.fillText(`Frame ${frame}/${maxFrames}`, 12, height - 12)
    },
    [drivers, maxFrames, telemetryData, trackBounds],
  )

  useEffect(() => {
    if (!playing || maxFrames === 0) {
      return
    }

    let active = true
    lastTimeRef.current = performance.now()

    function animate(now: number) {
      if (!active) {
        return
      }

      const delta = now - lastTimeRef.current
      lastTimeRef.current = now
      frameRef.current += (delta * speedRef.current) / 200

      if (frameRef.current >= maxFrames) {
        frameRef.current = 0
        setPlaying(false)
        setProgress(1)
        setCurrentFrame(maxFrames)
        draw(maxFrames - 1)
        return
      }

      const frame = Math.floor(frameRef.current)
      setProgress(frame / maxFrames)
      setCurrentFrame(frame)
      draw(frame)
      animationRef.current = requestAnimationFrame(animate)
    }

    animationRef.current = requestAnimationFrame(animate)

    return () => {
      active = false
      cancelAnimationFrame(animationRef.current)
    }
  }, [draw, maxFrames, playing])

  useEffect(() => {
    if (!loading && maxFrames > 0) {
      draw(0)
    }
  }, [draw, loading, maxFrames])

  function handleSeek(event: React.ChangeEvent<HTMLInputElement>) {
    const value = Number(event.target.value) / 1000
    const frame = Math.floor(value * maxFrames)
    frameRef.current = frame
    setProgress(value)
    setCurrentFrame(frame)
    draw(frame)
  }

  function togglePlay() {
    if (!playing) {
      if (frameRef.current >= maxFrames - 1) {
        frameRef.current = 0
      }
      setPlaying(true)
      return
    }
    setPlaying(false)
  }

  if (loading) {
    return <div className="py-20 text-center text-sm text-muted">Загрузка телеметрии повтора...</div>
  }

  if (drivers.length === 0) {
    return <div className="py-20 text-center text-sm text-muted">Повтор недоступен, пока для этой гонки нет телеметрии лучших кругов.</div>
  }

  return (
    <div className="page-stack">
      {raceInfo ? <RaceNav raceId={raceInfo.id} seasonId={raceInfo.season_id} trackName={raceInfo.track_name} round={raceInfo.round} /> : null}

      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Повтор</p>
            <h1 className="page-title">Траектории лучших кругов как чистый пространственный разбор.</h1>
            <p className="page-copy">
              Повтор это пространственная ветка слоя анализа. Он сделан для просмотра того, как разные пилоты движутся по
              трассе, еще до перехода к телеметрии по отдельным сэмплам.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={`/race/${raceId}/analysis`} className="ui-button-secondary">
                Назад к анализу
              </Link>
              <Link href={`/compare/${raceId}`} className="ui-button-tertiary">
                Сравнить круги
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Охват повтора</p>
            <p className="mt-3 text-2xl font-semibold text-text">{drivers.length} пилотов</p>
            <p className="mt-2 text-sm text-muted">{maxFrames} кадров захвачено по траекториям лучших кругов</p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Видимые пилоты</p>
          <p className="stat-value mono-data">{drivers.length}</p>
          <p className="mt-2 text-sm text-muted">Пилоты-люди с телеметрией, пригодной для повтора</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Кадры</p>
          <p className="stat-value mono-data">{maxFrames}</p>
          <p className="mt-2 text-sm text-muted">Глубина сэмплирования анимации</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Скорость воспроизведения</p>
          <p className="stat-value mono-data">{speed}x</p>
          <p className="mt-2 text-sm text-muted">Текущая скорость повтора</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Кадр</p>
          <p className="stat-value mono-data">{currentFrame}</p>
          <p className="mt-2 text-sm text-muted">Текущая позиция анимации</p>
        </div>
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Повтор трассы</p>
          <h2 className="mt-2 section-title">Анимированные траектории с короткими шлейфами пилотов.</h2>
        </div>
        <div className="p-5">
          <canvas ref={canvasRef} width={900} height={600} className="w-full rounded-[16px] bg-[#080c10]" style={{ aspectRatio: "3 / 2" }} />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="surface-panel p-5">
          <p className="eyebrow">Управление</p>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <button onClick={togglePlay} className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-surfaceAlt text-lg text-text transition-colors hover:border-borderStrong">
              {playing ? "II" : ">"}
            </button>
            <input type="range" min={0} max={1000} value={Math.round(progress * 1000)} onChange={handleSeek} className="min-w-[180px] flex-1 accent-[#e23a2e]" />
            <div className="flex items-center gap-2">
              {[0.5, 1, 2, 4].map((value) => (
                <button key={value} onClick={() => setSpeed(value)} className={speed === value ? "ui-button-secondary h-10 px-3" : "ui-button-tertiary"}>
                  {value}x
                </button>
              ))}
            </div>
          </div>
          <p className="mt-4 text-sm text-muted">Повтор строится на сохраненной телеметрии лучших кругов. Он нужен для пространственного разбора, а не как замена гоночной трансляции.</p>
        </div>

        <div className="surface-panel p-5">
          <p className="eyebrow">Легенда</p>
          <div className="mt-4 space-y-3">
            {drivers.map((driver) => (
              <div key={driver.vehicle_index} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: driver.team_color }} />
                  <span className="text-sm text-text">{driver.driver_name}</span>
                </div>
                <span className="text-sm text-muted">{driver.position ? `P${driver.position}` : "--"}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
