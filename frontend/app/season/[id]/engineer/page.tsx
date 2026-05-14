"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { useEffect, useRef, useState } from "react"

import { apiFetch } from "@/lib/api-client"

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

interface Message {
  role: "user" | "engineer"
  text: string
}

interface EngineerContext {
  player_name: string
  player_id: number | null
  season_id: number
  position: number | null
  total_points: number
  wins: number
  podiums: number
  dnfs: number
  fastest_laps: number
  races_played: number
  race_history: { round: number; track: string; position: number | null; points: number }[]
}

const QUICK_PROMPTS = [
  "В чем моя главная слабость в этом сезоне?",
  "Какие трассы стоили мне больше всего очков?",
  "На чем должна фокусироваться стратегия следующей гонки?",
  "Насколько я стабилен по сравнению с борьбой за титул?",
  "Суммируй мои самые сильные и самые слабые гоночные уикенды.",
]

export default function EngineerPage({ params }: { params: { id: string } }) {
  const seasonId = Number(params.id)
  const { data: session } = useSession()
  const userId = (session?.user as { id?: number } | undefined)?.id

  const [context, setContext] = useState<EngineerContext | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [includeAllHistory, setIncludeAllHistory] = useState(false)
  const [contextLoading, setContextLoading] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userId) {
      return
    }

    setContextLoading(true)

    apiFetch(`/api/lobby/${seasonId}/engineer?web_user_id=${userId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: EngineerContext | null) => {
        setContext(payload)
        if (payload && payload.races_played > 0) {
          setMessages([
            {
              role: "engineer",
              text: `Сезонный инженер онлайн для ${payload.player_name}. У вас ${payload.total_points} очков за ${payload.races_played} гонок${payload.position ? `, сейчас вы на P${payload.position}` : ""}. Спрашивайте про тренды сезона, слабые трассы, стратегию или стабильность.`,
            },
          ])
        }
      })
      .finally(() => setContextLoading(false))
  }, [seasonId, userId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  async function send(question?: string) {
    const nextQuestion = (question ?? input).trim()
    if (!nextQuestion || !userId) {
      return
    }

    setInput("")
    setMessages((current) => [...current, { role: "user", text: nextQuestion }])
    setLoading(true)

    try {
      const response = await apiFetch(`/api/lobby/${seasonId}/engineer/ask`, {
        method: "POST",
        body: JSON.stringify({
          web_user_id: userId,
          question: nextQuestion,
          include_all_history: includeAllHistory,
        }),
      })

      const payload = await response.json()
      setMessages((current) => [...current, { role: "engineer", text: payload.answer ?? "Ответ не был получен." }])
    } catch {
      setMessages((current) => [
        ...current,
        { role: "engineer", text: "Не удалось связаться с инженером. Попробуйте еще раз после восстановления API." },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!session) {
    return (
      <div className="page-stack">
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Сезонный инженер</p>
          <h1 className="mt-3 section-title">Войдите, чтобы открыть персонального гоночного инженера.</h1>
          <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
            Инженер это member-only слой. Он использует связанную идентичность пилота и историю сезона, чтобы отвечать на
            вопросы о форме, трассах, стратегии и прогрессе.
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

  if (!contextLoading && (!context || !context.player_id)) {
    return (
      <div className="page-stack">
        <section className="surface-panel p-8 text-center sm:p-10">
          <p className="eyebrow">Нужна привязка профиля</p>
          <h1 className="mt-3 section-title">Привяжите пилота лиги перед использованием инженера.</h1>
          <p className="mx-auto mt-4 max-w-[44ch] text-sm leading-7 text-muted">
            Этому инструменту нужна связанная идентичность игрока, чтобы подтягивать контекст сезона, историю гонок и ваши
            собственные performance-сигналы на базе телеметрии.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/me" className="ui-button-primary">
              Открыть центр аккаунта
            </Link>
            <Link href="/workspace" className="ui-button-tertiary">
              Открыть кабинет
            </Link>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="page-stack">
      <section className="surface-feature p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_320px] lg:items-end">
          <div className="space-y-4">
            <p className="eyebrow">Сезонный инженер</p>
            <h1 className="page-title">Персональный анализ, привязанный к истории чемпионата.</h1>
            <p className="page-copy">
              Инженер это guided-entry в AI-поверхности этого сезона. Он открывается вашим положением и контекстом
              результатов, а потом дает задавать точечные вопросы вместо мгновенного сброса в сырую аналитику.
            </p>
            <div className="flex flex-wrap gap-3">
              <label className="inline-flex items-center gap-2 rounded-full border border-border bg-surfaceAlt px-3 py-2 text-xs text-muted">
                <input
                  type="checkbox"
                  checked={includeAllHistory}
                  onChange={(event) => setIncludeAllHistory(event.target.checked)}
                  className="accent-[#e23a2e]"
                />
                Включить полную историю карьеры
              </label>
              <Link href={`/season/${seasonId}`} className="ui-button-tertiary">
                Назад к сезону
              </Link>
            </div>
          </div>

          <div className="surface-panel p-5">
            <p className="utility-kicker">Контекст инженера</p>
            <p className="mt-3 text-2xl font-semibold text-text">{context?.player_name ?? "Загрузка..."}</p>
            <p className="mt-2 text-sm text-muted">
              {context
                ? `${context.total_points} очков - ${context.races_played} гонок${context.position ? ` - P${context.position} в сезоне` : ""}`
                : "Ждем member-контекст"}
            </p>
          </div>
        </div>
      </section>

      <section className="summary-grid">
        <div className="stat-card">
          <p className="stat-label">Гонки</p>
          <p className="stat-value mono-data">{context?.races_played ?? 0}</p>
          <p className="mt-2 text-sm text-muted">Зафиксировано в этом сезоне</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Очки</p>
          <p className="stat-value mono-data">{context?.total_points ?? 0}</p>
          <p className="mt-2 text-sm text-muted">Итог по сезону</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Победы / подиумы</p>
          <p className="stat-value mono-data">
            {context?.wins ?? 0}/{context?.podiums ?? 0}
          </p>
          <p className="mt-2 text-sm text-muted">Главные результаты</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">DNFs / FL</p>
          <p className="stat-value mono-data">
            {context?.dnfs ?? 0}/{context?.fastest_laps ?? 0}
          </p>
          <p className="mt-2 text-sm text-muted">Маркеры риска и темпа</p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_320px]">
        <div className="surface-panel overflow-hidden">
          <div className="border-b border-border px-6 py-5">
            <p className="eyebrow">Диалог</p>
            <h2 className="mt-2 section-title">Задайте инженеру точечный вопрос.</h2>
          </div>

          <div className="flex max-h-[640px] min-h-[440px] flex-col">
            <div className="flex-1 space-y-3 overflow-y-auto p-6">
              {contextLoading ? <p className="py-8 text-center text-sm text-muted">Загрузка контекста сезона...</p> : null}

              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  {message.role === "engineer" ? (
                    <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent">
                      AI
                    </div>
                  ) : null}
                  <div
                    className={`max-w-[82%] rounded-[16px] px-4 py-3 text-sm leading-7 ${
                      message.role === "user" ? "bg-accent/14 text-text" : "bg-white/5 text-text"
                    }`}
                  >
                    {message.text}
                  </div>
                </div>
              ))}

              {loading ? (
                <div className="flex gap-3">
                  <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent">
                    AI
                  </div>
                  <div className="rounded-[16px] bg-white/5 px-4 py-3 text-sm text-muted">Анализируем данные сезона...</div>
                </div>
              ) : null}

              <div ref={bottomRef} />
            </div>

            {messages.length <= 1 && !contextLoading && (context?.races_played ?? 0) > 0 ? (
              <div className="border-t border-border px-6 py-4">
                <p className="mb-3 text-xs uppercase tracking-[0.18em] text-dim">Подсказки для старта</p>
                <div className="flex flex-wrap gap-2">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => send(prompt)}
                      className="rounded-full border border-border bg-surfaceAlt px-3 py-2 text-xs text-muted transition-colors hover:border-borderStrong hover:text-text"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="border-t border-border p-4">
              <div className="flex gap-3">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault()
                      send()
                    }
                  }}
                  placeholder="Спросите о темпе, стратегии, стабильности, слабых трассах или трендах борьбы за титул..."
                  disabled={loading || !context?.player_id}
                  className="h-12 flex-1 rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong disabled:opacity-50"
                />
                <button onClick={() => send()} disabled={!input.trim() || loading || !context?.player_id} className="ui-button-primary">
                  Отправить
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface-panel p-5">
            <p className="eyebrow">О чем спрашивать</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
              <li>Спрашивайте о слабостях на конкретных трассах, а не о мотивации в целом.</li>
              <li>Используйте инструмент перед гоночным вечером для рамки стратегии или после гонки для debrief-контекста.</li>
              <li>Включайте полную историю только когда хотите увидеть кросс-сезонные паттерны.</li>
            </ul>
          </div>

          {context?.race_history?.length ? (
            <div className="surface-panel p-5">
              <p className="eyebrow">Недавние этапы</p>
              <div className="mt-4 space-y-3">
                {context.race_history.slice(-4).reverse().map((entry) => (
                  <div key={`${entry.round}-${entry.track}`} className="rounded-[12px] border border-border bg-surfaceAlt/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-text">{entry.track}</p>
                      <span className="data-pill">R{entry.round}</span>
                    </div>
                    <p className="mt-2 text-sm text-muted">
                      {entry.position ? `Финиш P${entry.position}` : "Нет классифицированного финиша"} - {entry.points} очков
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}
