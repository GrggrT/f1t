"use client"

import Link from "next/link"
import { Suspense, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"

import { apiFetch } from "@/lib/api-client"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function JoinContent() {
  const { data: session, status } = useSession()
  const searchParams = useSearchParams()
  const router = useRouter()

  const userId = session?.user?.id ? Number(session.user.id) : undefined
  const codeFromUrl = searchParams.get("code") ?? ""

  const [code, setCode] = useState(codeFromUrl)
  const [joining, setJoining] = useState(false)
  const [error, setError] = useState("")

  async function handleJoin() {
    if (!code.trim() || !userId) {
      return
    }

    setJoining(true)
    setError("")

    try {
      const response = await apiFetch(`/api/lobby/join-by-code`, {
        method: "POST",
        body: JSON.stringify({ invite_code: code.trim() }),
      })
      const payload = await response.json()

      if (response.ok && payload.lobby_id) {
        router.push(`/lobby/${payload.lobby_id}`)
        return
      }

      setError(payload.detail || "Не удалось использовать код приглашения.")
    } catch {
      setError("Сетевая ошибка при входе в лобби.")
    } finally {
      setJoining(false)
    }
  }

  useEffect(() => {
    if (codeFromUrl && userId && status === "authenticated") {
      handleJoin()
    }
  }, [codeFromUrl, status, userId])

  if (status === "loading") {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка входа по инвайту...</div>
  }

  if (!session) {
    return (
      <div className="page-shell-narrow">
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Вступление по инвайту</p>
          <h1 className="mt-3 section-title">Сначала войдите, затем заходите в приватную группу лиги.</h1>
          <p className="mx-auto mt-4 max-w-[40ch] text-sm leading-7 text-muted">
            Инвайт-коды относятся к member-сценарию. Сначала нужна аутентификация, чтобы лобби сразу привязало ваш аккаунт
            к правильной роли.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/login" className="ui-button-primary">
              Войти
            </Link>
            <Link href="/launcher" className="ui-button-tertiary">
              Настройка лаунчера
            </Link>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="page-shell-narrow">
      <section className="surface-feature p-6 sm:p-8">
        <p className="eyebrow">Вступление по инвайту</p>
        <h1 className="page-title">Войдите в группу лиги по одному коду.</h1>
        <p className="page-copy">
          Это low-friction поверхность входа для участников. Сначала вступите в лобби, а потом уже переходите из кабинета в
          сезоны, таблицу и историю гонок.
        </p>
      </section>

      <section className="surface-panel p-6">
        <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-dim">Код приглашения</label>
        <input
          type="text"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleJoin()
            }
          }}
          placeholder="Вставьте код приглашения"
          className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
        />
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
        <div className="mt-5 flex flex-wrap gap-3">
          <button onClick={handleJoin} disabled={joining || !code.trim()} className="ui-button-primary">
            {joining ? "Вступаем..." : "Вступить в лобби"}
          </button>
          <Link href="/workspace" className="ui-button-tertiary">
            Назад в кабинет
          </Link>
        </div>
      </section>
    </div>
  )
}

export default function JoinLobbyPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка входа по инвайту...</div>}>
      <JoinContent />
    </Suspense>
  )
}
