import Link from "next/link"

interface CurrentSeason {
  id: number
  name: string
  status: string
}

const groups = [
  {
    heading: "Навигация",
    links: [
      { href: "/seasons", label: "Сезоны" },
      { href: "/races", label: "Гонки" },
      { href: "/players", label: "Игроки" },
      { href: "/records", label: "Рекорды" },
    ],
  },
  {
    heading: "Продукт",
    links: [
      { href: "/launcher", label: "Windows лаунчер" },
      { href: "/lobby/join", label: "Вступить" },
      { href: "/login", label: "Войти" },
    ],
  },
  {
    heading: "Участникам",
    links: [
      { href: "/workspace", label: "Кабинет" },
      { href: "/practice", label: "Практика" },
      { href: "/admin", label: "Админ" },
    ],
  },
]

export function SiteFooter({ currentSeason }: { currentSeason: CurrentSeason | null }) {
  return (
    <footer className="border-t border-border/80 bg-black/10">
      <div className="mx-auto max-w-[1360px] px-4 py-10 sm:px-6 lg:px-10">
        <div className="grid gap-4 border-b border-border pb-8 lg:grid-cols-3">
          <div className="surface-panel-muted p-5">
            <p className="utility-kicker">Публичный слой</p>
            <p className="mt-3 text-lg font-semibold text-text">Текущий сезон, архив и официальные результаты собраны в одном оболочечном слое.</p>
          </div>
          <div className="surface-panel-muted p-5">
            <p className="utility-kicker">Захват данных</p>
            <p className="mt-3 text-lg font-semibold text-text">Windows лаунчер отвечает за захват телеметрии и загрузку сессий.</p>
          </div>
          <div className="surface-panel-muted p-5">
            <p className="utility-kicker">Слой аккаунта</p>
            <p className="mt-3 text-lg font-semibold text-text">Аккаунт лиги связывает сайт, личность игрока и доступ к лаунчеру.</p>
          </div>
        </div>

        <div className="grid gap-10 pt-8 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,2fr)]">
          <div className="space-y-5">
            <div>
              <p className="eyebrow">F1 League</p>
              <h2 className="mt-3 font-display text-[2rem] leading-none tracking-[0.03em] text-text">
                Сайт лиги для текущего сезона, архива гонок и истории игроков.
              </h2>
            </div>
            <p className="max-w-[44rem] text-sm leading-7 text-muted">
              Публичный сайт остается читаемым слоем системы. Здесь живут таблицы чемпионата, сводки гонок, профили игроков и
              история сезонов, а лаунчер остается десктопным инструментом для захвата и загрузки.
            </p>

            <div className="flex flex-wrap gap-2">
              {currentSeason ? (
                <>
                  <span className="state-chip">{currentSeason.status === "active" ? "Текущий сезон" : "Статус сезона"}</span>
                  <Link href={`/season/${currentSeason.id}`} className="data-pill transition-colors hover:border-borderStrong hover:text-text">
                    {currentSeason.name}
                  </Link>
                </>
              ) : (
                <span className="data-pill">Архив сезонов доступен</span>
              )}
              <span className="data-pill">Windows лаунчер</span>
              <span className="data-pill">Профили игроков</span>
              <span className="data-pill">Официальные сводки гонок</span>
            </div>
          </div>

          <div className="grid gap-8 sm:grid-cols-3">
            {groups.map((group) => (
              <div key={group.heading} className="space-y-3">
                <p className="utility-kicker">{group.heading}</p>
                <div className="space-y-2">
                  {group.links.map((link) => (
                    <Link key={link.href} href={link.href} className="block text-sm text-muted transition-colors hover:text-text">
                      {link.label}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}
