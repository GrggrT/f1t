"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

interface RaceNavProps {
  raceId: number
  seasonId: number
  trackName: string
  round: number | null
}

export function RaceNav({ raceId, seasonId, trackName, round }: RaceNavProps) {
  const pathname = usePathname()

  const tabs = [
    { href: `/race/${raceId}`, label: "Результаты" },
    { href: `/race/${raceId}/analysis`, label: "Анализ" },
    { href: `/telemetry/${raceId}`, label: "Телеметрия" },
    { href: `/compare/${raceId}`, label: "Сравнение" },
    { href: `/race/${raceId}/replay`, label: "Повтор" },
  ]

  return (
    <div className="space-y-4">
      <div className="surface-panel-muted p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.18em] text-dim">
              <Link href="/" className="transition-colors hover:text-text">
                Home
              </Link>
              <span>/</span>
              <Link href="/races" className="transition-colors hover:text-text">
                Гонки
              </Link>
              <span>/</span>
              <Link href={`/season/${seasonId}`} className="transition-colors hover:text-text">
                Сезон
              </Link>
              <span>/</span>
              <span className="text-muted">{trackName}</span>
            </nav>
            <div>
              <p className="eyebrow">Сводка гонки</p>
              <h1 className="mt-2 font-display text-[2rem] leading-none tracking-[0.05em] text-text">{trackName}</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {round ? <span className="state-chip">Раунд {round}</span> : null}
            <span className="data-pill">Официальный результат</span>
          </div>
        </div>
      </div>

      <div className="sticky top-[110px] z-40 overflow-x-auto rounded-[14px] border border-border bg-bg/92 p-2 backdrop-blur">
        <div className="flex min-w-max gap-1">
          {tabs.map((tab) => {
            const isActive = tab.href === `/race/${raceId}` ? pathname === tab.href : pathname.startsWith(tab.href)
            return (
              <Link key={tab.href} href={tab.href} className={`subnav-link ${isActive ? "subnav-link-active" : ""}`}>
                {tab.label}
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
