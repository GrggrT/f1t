"use client"

import { useState } from "react"
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"

import { apiFetch } from "@/lib/api-client"

export function CreateLobbyButton() {
  const { data: session } = useSession()
  const router = useRouter()
  const token = session?.user?.backendToken

  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")

  if (!token) {
    return null
  }

  async function handleCreate() {
    if (!name.trim() || !token) {
      return
    }

    setCreating(true)
    setError("")

    try {
      const response = await apiFetch(`/api/lobby`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), description: description.trim() || undefined }),
      })

      if (response.ok) {
        const payload = await response.json()
        setOpen(false)
        setName("")
        setDescription("")
        router.push(`/lobby/${payload.id}`)
        router.refresh()
        return
      }

      const payload = await response.json().catch(() => ({}))
      setError(payload.detail || "Не удалось создать группу.")
    } catch {
      setError("Сетевая ошибка при создании группы.")
    } finally {
      setCreating(false)
    }
  }

  return (
    <>
      <button onClick={() => setOpen(!open)} className="ui-button-tertiary">
        Создать группу
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" onClick={() => setOpen(false)}>
          <div className="surface-panel w-full max-w-md p-6" onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">Создать группу</p>
            <h3 className="mt-2 section-title">Запустите новое пространство лобби.</h3>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-dim">Название</label>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Например: F1 League 2026"
                  className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                  autoFocus
                />
              </div>

              <div>
                <label className="mb-2 block text-xs uppercase tracking-[0.18em] text-dim">Описание</label>
                <input
                  type="text"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Необязательно"
                  className="h-12 w-full rounded-[12px] border border-border bg-[#0f141a] px-4 text-sm text-text outline-none transition-colors focus:border-borderStrong"
                />
              </div>

              {error ? <p className="text-sm text-danger">{error}</p> : null}

              <div className="flex justify-end gap-3">
                <button onClick={() => setOpen(false)} className="ui-button-tertiary">
                  Отмена
                </button>
                <button onClick={handleCreate} disabled={creating || !name.trim()} className="ui-button-primary">
                  {creating ? "Создание..." : "Создать"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
