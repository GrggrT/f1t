import { redirect } from "next/navigation"
import { getCurrentSeasonContext } from "@/lib/site-data"

export default async function LiveRedirect() {
  const { activeSeason } = await getCurrentSeasonContext()
  redirect(activeSeason ? `/season/${activeSeason.id}/live` : "/seasons")
}
