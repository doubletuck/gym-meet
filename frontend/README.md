# Gym Meet front end

The public website for browsing elite artistic gymnastics results. It reads
everything from the backend's public API (`backend/docs/api/`) and changes
nothing.

Built with React Router 8 on Vite, React and TypeScript, TanStack Query for
loading data, and Tailwind CSS. It runs as a single-page app for now
(`ssr: false` in `react-router.config.ts`); pages can be pre-rendered later for
link previews.

## Running locally

Requires Node 24. Start the backend first (`backend/docs/development-run.md`);
the dev server forwards `/api` requests to it on port 8080.

```shell
npm install
npm run dev
```

The site is at http://localhost:5173.

If a page stays on "Loading…", the browser is likely holding a stale copy of a
script from before the dev server finished preparing its dependencies (usually
the first run after `npm install`). Reload without the cache: Cmd+Shift+R in
Chrome; in Safari, Develop → Empty Caches, then Option+Cmd+R.

## Commands

| Command | Does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm test` | Runs the tests (Vitest) |
| `npm run typecheck` | Generates route types and checks TypeScript |
| `npm run build` | Production build into `build/client/` |
| `npm run format` | Formats the code with Prettier |
| `npm run api:types` | Regenerates `app/api/schema.d.ts` from the running backend's OpenAPI spec |

Run `npm run api:types` after changing the backend's API, with the backend
running, and commit the regenerated file.

## Layout

| Path | Holds |
|---|---|
| `app/routes.ts` | The pages and their addresses |
| `app/routes/` | Events list (`/`), an event (`/events/:eventSlug`), a session's results (`/events/:eventSlug/:discipline/:ageCategory/:sessionSlug`, e.g. `/events/2026-world-championships/wag/sr/beam-final`), athlete search (`/athletes?q=`) and an athlete's page (`/athletes/:athleteId`) |
| `app/api/` | The typed API client, its queries, and the generated types |
| `app/components/results/` | The results tables, which sort by a tapped column header. On a phone the values of the hidden columns are listed under the gymnast or team (D, E, bonus and penalty; or the apparatus scores); a vault final puts each gymnast's two vaults on two lines. A championship qualification's vault is two views: the first vault, which counts for team and all-around, and the two-vault ranking for the vault final. A round held in parts (a two-day all-around) shows each part's scores, labelled P1, P2, under the combined ones. Gymnast names link to their athlete pages. Gymnasts are shown with their club where the entry names one (national meets), the flag standing for the country, and with their country otherwise. Rows expand on tap only where there is more to show |
| `app/components/athletes/` | The athlete page's personal bests, and their results at each meet by session; each links to the results page it came from |
| `app/components/Abbreviation.tsx` | Short forms with their full form as a tooltip. Apparatus are shown everywhere outside headings and session names by their FIG code (VT, UB, BB, FX, PH, SR, PB, HB; VT1 and VT2 for two vaults), which screen readers read out in full ("Pommel Horse") |
| `app/components/ThemeToggle.tsx` | The header's System / Light / Dark switch. A picked theme is remembered in the browser; System (the default) follows the device and changes with it |
| `app/lib/` | Labels, country names and flags (by IOC code; flags from `flag-icons`, by ISO code), number and date formatting, and the theme choice. Dark styles key on a `dark` class on `<html>` (set in `app.css`), which a script in the page head applies before the first paint so a remembered theme shows without a flash |
