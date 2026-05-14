import Link from "next/link"

export interface BreadcrumbItem {
  href?: string
  label: string
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.18em] text-dim">
      {items.map((item, index) => {
        const isLast = index === items.length - 1
        return (
          <span key={`${item.label}-${index}`} className="flex items-center gap-2">
            {item.href && !isLast ? (
              <Link href={item.href} className="transition-colors hover:text-text">
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? "text-muted" : "text-dim"}>{item.label}</span>
            )}
            {!isLast && <span className="text-dim/70">/</span>}
          </span>
        )
      })}
    </nav>
  )
}
