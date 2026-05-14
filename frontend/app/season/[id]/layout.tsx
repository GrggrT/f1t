import { api } from "@/lib/api"
import { SeasonNav } from "@/components/SeasonNav"
import { notFound } from "next/navigation"

export default async function SeasonLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: { id: string }
}) {
  const seasonId = Number(params.id)
  const season = await api.season(seasonId).catch(() => null)

  if (!season) {
    notFound()
  }

  return (
    <div className="page-stack">
      <SeasonNav seasonId={season.id} seasonName={season.name} status={season.status} lobbyId={season.lobby_id} />
      {children}
    </div>
  )
}
