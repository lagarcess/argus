# Trinity Journal - Frontend Speedrun (Unblocking the UI)

## Context
The Python backend is currently under reconstruction and considered broken. To unblock frontend development and establish a type-safe, mock-driven environment, we decoupled the UI from the backend completely.

## Approach
1. **Type-Safe Generation**: Utilized `@hey-api/openapi-ts` with the `@tanstack/react-query` plugin to parse the existing `docs/api/openapi.yaml`. This generated fully-typed TypeScript fetch clients and `useQuery`/`useMutation` hooks in `web/lib/api`.
2. **Mock-Driven Environment**: Deployed `@stoplight/prism-cli` (`prism mock`) on port 4010 to serve spec-compliant responses dynamically. We intercepted Next.js server requests using this URL.
3. **UI Reconstruction (Stitch)**: Leveraged the Stitch AI agent to generate the "Strategy Builder v1" and "Simulation History" pages based on the *Obsidian Prism* and *Emerald Zenith* themes, targeting a high-tech "Robinhood/Linear" glassmorphic aesthetic.
4. **Data Wiring & Verification**: Stripped out legacy hardcoded data from `mockApi.ts`. Wired the generated components directly to the TanStack queries. To verify the setup, a Playwright test (`v1-ecosystem.vrt.ts`) was added that successfully stubs the Supabase auth session and performs end-to-end interactions with the mock-driven UI.

## Outcomes
- Frontend development can now proceed continuously without relying on a functional Python server.
- The UI components correctly interact with mock API endpoints utilizing strict `Zod`-like typing from the OpenAPI spec, eliminating undefined property crashes.
- The Golden Path Playwright E2E tests pass reliably in the CI-like headless mode.
