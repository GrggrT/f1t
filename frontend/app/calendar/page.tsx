import { redirect } from "next/navigation"
import { getCurrentSeasonContext } from "@/lib/site-data"

export default async function CalendarRedirect() {
  const { activeSeason } = await getCurrentSeasonContext()
  redirect(activeSeason ? `/season/${activeSeason.id}/calendar` : "/seasons")
}
