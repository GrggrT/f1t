import "next-auth"
import "next-auth/jwt"

declare module "next-auth" {
  interface Session {
    user: {
      id:           string
      name?:        string | null
      email?:       string | null
      image?:       string | null
      playerId:     number | null
      backendToken: string | null
    }
  }
  interface User {
    id:           string
    name?:        string | null
    email?:       string | null
    image?:       string | null
    player_id:    number | null
    backendToken: string | null
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    userId:       string
    playerId:     number | null
    backendToken: string | null
  }
}
