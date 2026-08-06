# Usage Allowance Meter Colors

Color the existing message and backtest allowance gauges from the user's real
near-term remaining capacity without changing allowance truth or adding alarmist
UI.

Founder-locked 2026-08-06, after clarifying consumed-capacity boundaries for
the standing active-roadmap chore.

## 1. Why

Argus must make limits understandable without becoming a trading terminal.
`docs/PRODUCT.md` makes Settings a supporting surface and names trust through
clarity as a product requirement. `.agent/designs/argus/DESIGN.md` section 23
requires allowance color to support, never replace, exact count and reset truth.

## 2. Locked decisions

1. Messages and backtests classify independently. A resource's windows never
   affect the other resource's gauge.
2. For each resource, normalize every active `hour` and `day` window as
   `remaining / limit`, clamp the result to `0..1`, and use the lowest ratio.
3. A missing window is inactive and is excluded. Registered accounts already
   receive both windows; guests truthfully receive only `day`.
4. Teal (`--rui-color-teal`) applies when at least 30% remains, including
   exactly 30%, which means at most 70% has been consumed.
5. Warning (`--rui-color-warning`) applies when more than 10% and less than 30%
   remains, which means consumption is above 70% and below 90%.
6. Danger (`--rui-color-danger`) applies when 10% or less remains, including
   exactly 10% and exhaustion, which means consumption is at least 90%.
7. The existing daily count, daily reset time, progressbar value, and conditional
   hourly count/reset detail remain visible and backend-owned.
8. No tone names, flashing, pulsing, repeated scaling, or terminal-style chrome
   are added. Color remains supporting information.
9. English and `es-419` keep equivalent calm copy. No user-facing copy may use
   an em dash.
10. The six durable captures cover teal, warning, and danger in English and
    `es-419`. English uses light theme and Spanish uses dark theme so both
    supported themes are verified within the founder-requested six captures.

## 3. Reserved / parked scope

- Backend allowance arithmetic and admission policy stay unchanged because the
  existing response already provides the required limits, remaining counts,
  and exact reset timestamps.
- The backend `limiting_window` field stays authoritative for the existing
  hourly-detail disclosure. The meter color separately follows the normalized
  display rule locked above.
- No quota percentages or countdown timers are added to user-facing copy.
- No profile-menu layout redesign is included. `ProfileMenu.tsx` only opens the
  modal; the meter renders in `UsageModal.tsx`.

## 4. Contract gates

- `.agent/designs/argus/DESIGN.md` section 23: align the documented boundaries
  with the founder clarification.
- `docs/specs/argus-active-roadmap.md`: align the standing chore summary with
  the same boundaries.
- `docs/API_CONTRACT.md`: no response-shape change.
- `docs/DATA_MODEL.md`: no persistence change.
- OpenAPI: no schema change, so regeneration is not required.

## 5. Execution contract

- **Branch shape:** one normal feature branch from fetched
  `origin/codex/private-alpha-next` SHA
  `9664e221fa50187d6b078ccdfcffd90cbc76d852`.
- **Proof required:** focused red-green unit coverage, the full frontend suite,
  lint, production build, merged-tree modularity check, and six durable browser
  captures showing count and reset time beside each threshold color in English
  light theme and Spanish dark theme.
- **Where it stops:** commit and push the worker branch. Do not merge, deploy,
  or create a pull request unless the founder separately requests it.

## 6. Stop conditions

- If registered allowance responses do not expose both active hourly and daily
  windows with `limit`, `remaining`, and `period_end`, stop and report.
- If the feature requires invented quota data, a backend/schema change, or a
  client-generated reset time, stop and report.
- If the exact thresholds cannot be implemented without removing the visible
  count or reset truth, stop and report.
- If local browser proof would spend a real provider turn or real backtest,
  stop and use the existing mocked route harness only.

## Sources

### Argus authority

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`, `GET /me/usage`
- `docs/DATA_MODEL.md`, section 14
- `.agent/designs/argus/DESIGN.md`, section 23
- `docs/specs/argus-active-roadmap.md`

### External inspiration

- None. This is a founder-locked Argus design.

### Inference

- Defining the semantic CSS custom properties in the global token root is the
  smallest way to make the binding token names real across both themes.
