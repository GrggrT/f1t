"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession } from "next-auth/react"
import { useEffect, useState } from "react"

import { apiFetch } from "@/lib/api-client"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface Props {
  seasonId: number
  seasonName: string
  status: string
  lobbyId?: number | null
}

type Role = "admin" | "moderator" | "member" | "guest"

function statusLabel(status: string) {
  if (status === "active") return "Текущий сезон"
  if (status === "finished") return "Завершен"
  if (status === "archived") return "Архив"
  return status
}

export function SeasonNav({ seasonId, seasonName, status, lobbyId }: Props) {
  const pathname = usePathname()
  const { data: session } = useSession()
  const [role, setRole] = useState<Role>("guest")
  const userId = session?.user?.id
  const base = `/season/${seasonId}`

  useEffect(() => {
    if (!userId || !lobbyId) {
      setRole("guest")
      return
    }

    apiFetch(`/api/lobby/${lobbyId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (payload?.your_role) {
          setRole(payload.your_role)
        }
      })
      .catch(() => {})
  }, [lobbyId, userId])

  const tabs = [
    { href: base, label: "Обзор" },
    { href: `${base}/standings`, label: "Таблица" },
    { href: `${base}/calendar`, label: "Календарь" },
    { href: `${base}/live`, label: "Live" },
    ...(session?.user ? [{ href: `${base}/engineer`, label: "Инженер" }] : []),
    // "Управление" tab hidden — manage UI is stubbed per PR 1.2.5
    // until Sprint 4 ships the redesigned season-management page.
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
              <Link href="/seasons" className="transition-colors hover:text-text">
                Сезоны
              </Link>
              <span>/</span>
              <span className="text-muted">{seasonName}</span>
            </nav>
            <div>
              <p className="eyebrow">Обзор сезона</p>
              <h1 className="mt-2 font-display text-[2rem] leading-none tracking-[0.05em] text-text">{seasonName}</h1>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="state-chip">{statusLabel(status)}</span>
            {(role === "admin" || role === "moderator") && (
              <span className="data-pill">{role === "admin" ? "Доступ оператора" : "Доступ модератора"}</span>
            )}
          </div>
        </div>
      </div>

      <div className="sticky top-[110px] z-40 overflow-x-auto rounded-[14px] border border-border bg-bg/92 p-2 backdrop-blur">
        <div className="flex min-w-max gap-1">
          {tabs.map((tab) => {
            const isActive = tab.href === base ? pathname === base || pathname === `${base}/` : pathname.startsWith(tab.href)
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`subnav-link ${isActive ? "subnav-link-active" : ""}`}
              >
                {tab.label}
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
