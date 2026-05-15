# WebUser + Player → User merge analysis

Generated at: 20260515-150258 UTC
Database URL: `postgres:5432/f1league`

## Counts

- `web_users` total: **5**
- `players` total: **1**
- linked pairs (web_users.player_id IS NOT NULL): **4**
- web-only (web_user without player): **1**
- player-only (player without web_user): **0**

## Web users with NULL email

- ⚠️ 1 row(s) (informational, not blocking):
  - id=2 name='Banana' google=None steam=76561198050754234 player_id=1

## Multiple WebUsers per player_id (BLOCKER if any)

- 🔴 player_id=1 has 4 web_users: [2, 1, 3, 5]

## Steam ID mismatch on linked pairs (BLOCKER if any)

- ✅ none

## Name mismatches on linked pairs (informational)

- ℹ️  3 pair(s) — Player.name wins per spec COALESCE:
  - web_user=2 web_name='Banana' → player=1 player_name='Serhii Hryhorenko'
  - web_user=1 web_name='Test User' → player=1 player_name='Serhii Hryhorenko'
  - web_user=5 web_name='PR11 Smoke' → player=1 player_name='Serhii Hryhorenko'

## Expected user count after merge

- linked (4) + web-only (1) + player-only (0) = **5**
