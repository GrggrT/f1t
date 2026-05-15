# WebUser + Player → User merge analysis

Generated at: 20260515-152845 UTC
Database URL: `postgres:5432/f1league`

## Counts

- `web_users` total: **5**
- `players` total: **1**
- linked pairs (web_users.player_id IS NOT NULL): **1**
- web-only (web_user without player): **4**
- player-only (player without web_user): **0**

## Web users with NULL email

- ⚠️ 1 row(s) (informational, not blocking):
  - id=2 name='Banana' google=None steam=76561198050754234 player_id=None

## Multiple WebUsers per player_id (BLOCKER if any)

- ✅ none

## Steam ID mismatch on linked pairs (BLOCKER if any)

- ✅ none

## Name mismatches on linked pairs (informational)

- ✅ none — names align across linked pairs

## Expected user count after merge

- linked (1) + web-only (4) + player-only (0) = **5**
