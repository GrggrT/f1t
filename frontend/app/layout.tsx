import type { Metadata } from "next"
import { IBM_Plex_Mono, IBM_Plex_Sans, Roboto_Condensed } from "next/font/google"
import "./globals.css"
import { Nav } from "@/components/Nav"
import { Providers } from "@/components/Providers"
import { SiteFooter } from "@/components/SiteFooter"
import { getSeasonShellData } from "@/lib/site-data"

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
})

const displayFont = Roboto_Condensed({
  subsets: ["latin", "cyrillic"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
})

const monoFont = IBM_Plex_Mono({
  subsets: ["latin", "cyrillic"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
})

export const metadata: Metadata = {
  title: {
    default: "F1 League",
    template: "%s | F1 League",
  },
  description:
    "Сезонный центр чемпионата, история гонок, телеметрия, лаунчер и операционный слой для любительской F1-лиги.",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { activeSeason } = await getSeasonShellData()

  return (
    <html lang="ru" suppressHydrationWarning>
      <body className={`${bodyFont.variable} ${displayFont.variable} ${monoFont.variable}`}>
        <Providers>
          <div className="min-h-screen">
            <Nav currentSeason={activeSeason} />
            <main className="mx-auto w-full max-w-[1360px] px-4 pb-20 pt-8 sm:px-6 sm:pt-10 lg:px-10 lg:pt-12">
              {children}
            </main>
            <SiteFooter currentSeason={activeSeason} />
          </div>
        </Providers>
      </body>
    </html>
  )
}
