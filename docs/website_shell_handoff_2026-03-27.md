# Website Shell Handoff (2026-03-27)

## Summary

- The website was rebuilt from a lobby-first collection of screens into a season-first hybrid product shell.
- Russian is now the default UI language for the web layer.
- The shell now separates public/product, competition, deep-analysis, member/workspace, and operator surfaces.

## Primary route model

### Public / Product
- `/` — homepage with Current Season Cockpit
- `/launcher` — launcher install, setup, trust, FAQ
- `/seasons` — season archive and discovery
- `/races` — race archive and discovery
- `/players` — player directory
- `/records` — evergreen records and achievements

### Competition
- `/season/[id]` — season overview
- `/season/[id]/standings`
- `/season/[id]/calendar`
- `/season/[id]/live`
- `/season/[id]/engineer`
- `/race/[id]` — race results

### Deep analysis
- `/race/[id]/analysis`
- `/telemetry/[race_id]`
- `/compare/[race_id]`
- `/race/[id]/replay`

### Member / Workspace
- `/workspace`
- `/me`
- `/lobby/[id]`
- `/lobby/join`
- `/login`

### Operator
- `/admin`
- `/season/[id]/manage`

## Navigation model

- Primary top nav: `Home`, `Seasons`, `Races`, `Players`, `Records`, `Launcher`, `Workspace`
- Canonical object flow: `Home -> Seasons -> Season -> Race`
- Season subnav: `Overview`, `Standings`, `Calendar`, `Live`, `Engineer`, `Manage` (role-gated)
- Race subnav: `Results`, `Analysis`, `Telemetry`, `Compare`, `Replay`
- Breadcrumbs are present on season, race, telemetry, player, and operator/deep pages

## Locale / visual foundation

- `frontend/app/layout.tsx`
  - `lang="ru"`
  - Cyrillic-safe font stack: `IBM Plex Sans`, `IBM Plex Mono`, `Roboto Condensed`
- `frontend/lib/utils.ts`
  - date formatting uses `ru-RU`
- Shared shell localized:
  - `frontend/components/Nav.tsx`
  - `frontend/components/SiteFooter.tsx`
  - `frontend/components/SeasonNav.tsx`
  - `frontend/components/RaceNav.tsx`
- Secondary UI localized:
  - `frontend/app/CreateLobbyButton.tsx`
  - `frontend/components/PlayerBadge.tsx`
  - `frontend/app/profile/[id]/achievements.ts`

## Compatibility redirects

- `/agent` -> `/launcher`
- `/profile/[id]` -> `/players/[id]`
- `/calendar` -> active season calendar
- `/standings` -> active season standings
- `/live` -> active season live

## Validation

- `npm run build` passed in `C:\f1t\frontend`

## Known follow-up

- English is not yet implemented as a real runtime toggle; the current website is Russian-first.
- A true `RU/EN` mode will require extracting inline copy into dictionaries and adding an explicit i18n layer.
- Domain abbreviations such as `WDC`, `WCC`, `DRS`, `ERS`, `DNF`, and `FL` remain intentionally untranslated where they are clearer as motorsport shorthand.
