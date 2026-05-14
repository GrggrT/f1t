import type { ReactNode } from "react"

interface PageIntroProps {
  eyebrow: string
  title: string
  description: ReactNode
  actions?: ReactNode
  meta?: ReactNode
}

export function PageIntro({ eyebrow, title, description, actions, meta }: PageIntroProps) {
  return (
    <section className="surface-feature p-6 sm:p-7 lg:p-9">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="space-y-4">
          <p className="eyebrow">{eyebrow}</p>
          <div className="space-y-3">
            <h1 className="page-title">{title}</h1>
            <div className="page-copy">{description}</div>
          </div>
        </div>
        {actions && <div className="flex flex-wrap gap-3 lg:justify-end">{actions}</div>}
      </div>
      {meta ? <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-5">{meta}</div> : null}
    </section>
  )
}
