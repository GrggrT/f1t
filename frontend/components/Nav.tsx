"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession } from "next-auth/react"

interface CurrentSeason {
  id: number
  name: string
  status: string
}

interface NavLinkItem {
  href: string
  label: string
  active: (pathname: string) => boolean
}

function isWithinSection(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`)
}

function buildPrimaryLinks(currentSeason: CurrentSeason | null): NavLinkItem[] {
  const currentSeasonHref = currentSeason ? `/season/${currentSeason.id}` : "/seasons"

  return [
    {
      href: currentSeasonHref,
      label: "Текущий сезон",
      active: (pathname) => (currentSeason ? isWithinSection(pathname, currentSeasonHref) : pathname === "/seasons"),
    },
    {
      href: "/seasons",
      label: "Сезоны",
      active: (pathname) => pathname === "/seasons" || (pathname.startsWith("/season/") && (!currentSeason || !isWithinSection(pathname, currentSeasonHref))),
    },
    {
      href: "/races",
      label: "Гонки",
      active: (pathname) => pathname === "/races" || pathname.startsWith("/race/") || pathname.startsWith("/compare/") || pathname.startsWith("/telemetry/"),
    },
    {
      href: "/players",
      label: "Игроки",
      active: (pathname) => pathname === "/players" || pathname.startsWith("/players/") || pathname.startsWith("/profile/"),
    },
    {
      href: "/records",
      label: "Рекорды",
      active: (pathname) => pathname === "/records" || pathname.startsWith("/records/"),
    },
    {
      href: "/launcher",
      label: "Лаунчер",
      active: (pathname) => pathname === "/launcher" || pathname.startsWith("/agent/"),
    },
  ]
}

export function Nav({ currentSeason }: { currentSeason: CurrentSeason | null }) {
  const pathname = usePathname()
  const { data: session } = useSession()
  const primaryLinks = buildPrimaryLinks(currentSeason)

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-bg/94 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1360px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-10">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-borderStrong bg-surfaceAlt text-sm font-semibold uppercase tracking-[0.18em] text-text">
            F1
          </div>
          <div className="min-w-0">
            <div className="font-display text-[1.72rem] leading-none tracking-[0.04em] text-text">League</div>
            <div className="truncate text-[10px] uppercase tracking-[0.22em] text-dim">
              {currentSeason ? `Текущий сезон: ${currentSeason.name}` : "Архив сезонов и история гонок"}
            </div>
          </div>
        </Link>

        <nav className="hidden flex-1 items-center justify-center xl:flex" aria-label="Primary">
          <div className="flex items-center gap-1 rounded-[14px] border border-border bg-surface/75 p-1">
            {primaryLinks.map((link) => {
              const active = link.active(pathname)
              return (
                <Link key={link.href} href={link.href} className={`subnav-link ${active ? "subnav-link-active" : ""}`}>
                  {link.label}
                </Link>
              )
            })}
          </div>
        </nav>

        <div className="flex items-center gap-2">
          <Link href="/lobby/join" className="ui-button-tertiary hidden sm:inline-flex">
            Вступить
          </Link>

          {session?.user ? (
            <Link
              href="/workspace"
              className="flex items-center gap-2 rounded-[12px] border border-border bg-surfaceAlt px-2.5 py-2 transition-colors hover:border-borderStrong hover:bg-panel"
            >
              {session.user.image ? (
                <img src={session.user.image} alt="" className="h-8 w-8 rounded-full object-cover" />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/20 text-sm font-semibold text-accent">
                  {(session.user.name ?? "?").charAt(0).toUpperCase()}
                </div>
              )}
              <div className="hidden text-left sm:block">
                <div className="max-w-[140px] truncate text-sm font-medium text-text">{session.user.name ?? "Кабинет"}</div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-dim">Кабинет</div>
              </div>
            </Link>
          ) : (
            <Link href="/login" className="ui-button-primary h-10 px-4 text-sm">
              Войти
            </Link>
          )}
        </div>
      </div>

      <div className="border-t border-border/70 xl:hidden">
        <div className="mx-auto flex max-w-[1360px] gap-1 overflow-x-auto px-4 py-2 sm:px-6 lg:px-10">
          {primaryLinks.map((link) => {
            const active = link.active(pathname)
            return (
              <Link key={link.href} href={link.href} className={`subnav-link whitespace-nowrap ${active ? "subnav-link-active" : ""}`}>
                {link.label}
              </Link>
            )
          })}
        </div>
      </div>
    </header>
  )
}
