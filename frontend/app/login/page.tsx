"use client"

import Link from "next/link"
import { signIn, useSession } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

function LoginContent() {
  const { status } = useSession()
  const router = useRouter()
  const params = useSearchParams()

  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const launcherId = params.get("launcher")

  useEffect(() => {
    const steamToken = params.get("steam_token")
    if (steamToken) {
      signIn("steam", { steam_token: steamToken, callbackUrl: "/workspace" })
      return
    }

    const nextError = params.get("error")
    if (nextError === "steam_invalid") setError("Не удалось войти через Steam. Попробуйте еще раз.")
    if (nextError === "steam_error") setError("Не удалось завершить подключение Steam.")
  }, [params])

  useEffect(() => {
    if (status !== "authenticated") {
      return
    }

    if (launcherId) {
      const sendToLauncher = async () => {
        try {
          const sessionResponse = await fetch("/api/auth/session")
          const sessionPayload = await sessionResponse.json()
          const userId = sessionPayload?.user?.id

          if (userId) {
            await fetch(`${API}/api/web/launcher/auth`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ poll_id: launcherId, user_id: Number(userId) }),
            })
          }
        } catch {
          // Launcher handoff is best-effort.
        }
      }

      sendToLauncher()
      return
    }

    router.push("/workspace")
  }, [API, launcherId, router, status])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)

    if (mode === "register") {
      const registerResponse = await fetch(`${API}/api/web/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      })

      if (!registerResponse.ok) {
        const payload = await registerResponse.json()
        setError(payload.detail ?? "Не удалось зарегистрироваться.")
        setLoading(false)
        return
      }
    }

    const result = await signIn("credentials", { email, password, redirect: false })
    setLoading(false)

    if (result?.error) {
      setError("Неверный email или пароль.")
      return
    }

    router.push("/workspace")
  }

  if (status === "loading") {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка входа...</div>
  }

  if (launcherId && status === "authenticated") {
    return (
      <div className="page-shell-narrow">
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Передача в лаунчер</p>
          <h1 className="mt-3 section-title">Вход завершен.</h1>
          <p className="mx-auto mt-4 max-w-[40ch] text-sm leading-7 text-muted">
            Лаунчер должен автоматически подхватить эту сессию. Можно закрыть окно браузера и вернуться в десктопное
            приложение.
          </p>
        </section>
      </div>
    )
  }

  return (
    <div className="page-shell-narrow">
      <section className="surface-feature p-6 sm:p-8">
        <p className="eyebrow">Аутентификация</p>
        <h1 className="page-title">Войдите, чтобы попасть в слой участников.</h1>
        <p className="page-copy">
          Авторизация на сайте нужна для кабинета, инвайтов в лобби, передачи сессии в лаунчер и привязки профиля игрока.
          Эта страница остается короткой и продуктовой, а не превращается в абстрактную форму аккаунта.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href="/launcher" className="ui-button-secondary">
            Настройка лаунчера
          </Link>
          <Link href="/" className="ui-button-tertiary">
            На главную
          </Link>
        </div>
      </section>

      <section className="surface-panel p-6">
        <div className="grid gap-6">
          <div className="grid gap-3">
            <button
              onClick={() => signIn("google", { callbackUrl: "/workspace" })}
              className="flex h-12 items-center justify-center gap-3 rounded-[12px] border border-[#c9d6ea] bg-white px-4 text-sm font-medium text-[#11161c] transition-colors hover:bg-[#eef3fb]"
            >
              <svg className="h-5 w-5 flex-shrink-0" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Продолжить через Google
            </button>

            <a
              href={`${API}/api/web/steam/start`}
              className="flex h-12 items-center justify-center gap-3 rounded-[12px] border border-[#36506f] bg-[#1b2838] px-4 text-sm font-medium text-[#c7d5e0] transition-colors hover:bg-[#2a475e]"
            >
              <svg className="h-5 w-5 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.979 0C5.678 0 .511 4.86.022 11.037l6.432 2.658c.545-.371 1.203-.59 1.912-.59.063 0 .125.004.188.006l2.861-4.142V8.91c0-2.495 2.028-4.524 4.524-4.524 2.494 0 4.524 2.029 4.524 4.527s-2.03 4.525-4.524 4.525h-.105l-4.076 2.911c0 .052.004.105.004.159 0 1.875-1.515 3.396-3.39 3.396-1.635 0-3.016-1.173-3.331-2.727L.436 15.27C1.862 20.307 6.486 24 11.979 24c6.627 0 11.999-5.373 11.999-12S18.605 0 11.979 0zM7.54 18.21l-1.473-.61c.262.543.714.999 1.314 1.25 1.297.539 2.793-.076 3.332-1.375.263-.63.264-1.319.005-1.949s-.75-1.121-1.377-1.383c-.624-.26-1.29-.249-1.878-.03l1.523.63c.956.4 1.409 1.5 1.009 2.455-.397.957-1.497 1.41-2.454 1.012H7.54zm11.415-9.303c0-1.662-1.353-3.015-3.015-3.015-1.665 0-3.015 1.353-3.015 3.015 0 1.665 1.35 3.015 3.015 3.015 1.663 0 3.015-1.35 3.015-3.015zm-5.273-.005c0-1.252 1.013-2.266 2.265-2.266 1.249 0 2.266 1.014 2.266 2.266 0 1.251-1.017 2.265-2.266 2.265-1.252 0-2.265-1.014-2.265-2.265z"/>
              </svg>
              Продолжить через Steam
            </a>
          </div>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-[0.18em] text-dim">или</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === "register" ? (
              <input
                type="text"
                placeholder="Отображаемое имя"
                value={name}
                required
                onChange={(event) => setName(event.target.value)}
                className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
              />
            ) : null}
            <input
              type="email"
              placeholder="Email"
              value={email}
              required
              onChange={(event) => setEmail(event.target.value)}
              className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
            />
            <input
              type="password"
              placeholder="Пароль"
              value={password}
              required
              onChange={(event) => setPassword(event.target.value)}
              className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
            />

            {error ? <p className="rounded-[12px] border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</p> : null}

            <button type="submit" disabled={loading} className="ui-button-primary w-full">
              {loading ? "Обработка..." : mode === "register" ? "Создать аккаунт" : "Войти"}
            </button>
          </form>

          <div className="rounded-[16px] border border-border bg-surfaceAlt/60 p-4 text-sm leading-7 text-muted">
            <p>Google и Steam это самые быстрые маршруты для входа участников.</p>
            <p>Email-авторизация остается доступной для прямого доступа к сайту и принятия инвайтов.</p>
          </div>

          <p className="text-center text-sm text-muted">
            {mode === "login" ? "Еще нет аккаунта?" : "Уже есть аккаунт?"}{" "}
            <button
              onClick={() => {
                setMode(mode === "login" ? "register" : "login")
                setError(null)
              }}
              className="text-accent transition-colors hover:text-text"
            >
              {mode === "login" ? "Создать" : "Войти"}
            </button>
          </p>
        </div>
      </section>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-[40vh] items-center justify-center text-sm text-muted">Загрузка входа...</div>}>
      <LoginContent />
    </Suspense>
  )
}
