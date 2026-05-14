import { redirect } from "next/navigation"

export default function LegacyProfileRedirect({ params }: { params: { id: string } }) {
  redirect(`/players/${params.id}`)
}
