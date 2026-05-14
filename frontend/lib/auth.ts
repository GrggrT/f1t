import type { NextAuthOptions } from "next-auth"
import GoogleProvider      from "next-auth/providers/google"
import CredentialsProvider from "next-auth/providers/credentials"

// В серверном коде (API routes) используем внутренний URL докера
const API = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? ""

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,

  providers: [
    GoogleProvider({
      clientId:     process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),

    // Email + пароль
    CredentialsProvider({
      id:   "credentials",
      name: "Email",
      credentials: {
        email:    { label: "Email",  type: "email" },
        password: { label: "Пароль", type: "password" },
      },
      async authorize(creds) {
        if (!creds?.email || !creds?.password) return null
        try {
          const r = await fetch(`${API}/api/web/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: creds.email, password: creds.password }),
          })
          if (!r.ok) return null
          const u = await r.json()
          return { id: String(u.id), name: u.name, email: u.email, image: u.picture, player_id: u.player_id, backendToken: u.token }
        } catch { return null }
      },
    }),

    // Steam — после Steam OpenID backend создаёт одноразовый код
    CredentialsProvider({
      id:   "steam",
      name: "Steam",
      credentials: { steam_token: { label: "Token", type: "text" } },
      async authorize(creds) {
        if (!creds?.steam_token) return null
        try {
          const r = await fetch(`${API}/api/web/steam-token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: creds.steam_token }),
          })
          if (!r.ok) return null
          const u = await r.json()
          return { id: String(u.id), name: u.name, email: u.email, image: u.picture, player_id: u.player_id, backendToken: u.token }
        } catch { return null }
      },
    }),
  ],

  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google") {
        try {
          const r = await fetch(`${API}/api/web/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              google_id: account.providerAccountId,
              email:     user.email,
              name:      user.name,
              picture:   user.image,
            }),
          })
          if (r.ok) {
            const data = await r.json()
            user.id                      = String(data.id)
            ;(user as any).player_id     = data.player_id ?? null
            ;(user as any).backendToken  = data.token ?? null
          }
        } catch {}
      }
      return true
    },

    async jwt({ token, user }) {
      if (user) {
        token.userId       = user.id
        token.playerId     = (user as any).player_id ?? null
        token.backendToken = (user as any).backendToken ?? null
      }
      return token
    },

    async session({ session, token }) {
      session.user.id           = token.userId as string
      session.user.playerId     = (token.playerId as number | null) ?? null
      session.user.backendToken = (token.backendToken as string | null) ?? null
      return session
    },
  },

  pages: {
    signIn: "/login",
    error:  "/login",
  },

  session: { strategy: "jwt" },
}
