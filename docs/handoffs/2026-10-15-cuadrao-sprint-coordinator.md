# Cuadrao sprint coordinator handoff, October 15, 2026

The coordinator wound down at the founder's request on October 15, 2026, near the usage limit.
This file records the exact state for the next coordinator. Read it with the
[execution manifest](../specs/argus-execution-board.md) and the
[Business handoff](cuadrao-business-lane.md).

## Integration tip

- Branch `codex/private-alpha-next`, tip `2b2665d63` (#1161).
- Tip checks: CI 38843052942 and Private Alpha Local Smoke 38843052978 were still running at wind-down. The previous tip `e0a0706ad` passed Local Smoke 38840944565.
- Staging API and web were last confirmed live at `63d6f0135` (#1153). Later commits deploy automatically. Check `render deploys list` before you rely on staging.

## Landed this sprint

Each PR was squashed with `--match-head-commit` after an independent Eval passed the exact head.

| PR | What it does | Squash |
|---|---|---|
| #1121 | Consumer lane into integration | `f7f6a8b52` |
| #1088 | Fiscal totals, Sin comprobante fiscal, Personal mark, 606 answer | `a76d5b6cb` |
| #1126 | One review page, one server count, RNC desconocido (#1113) | `6053679dd` |
| #1128 | Invited accountant sees the client on first sign-in | `b573ce14a` |
| #1129 | Spanish guest journey test fix (#1127) | `a9a61e88d` |
| #1125 | Launch logo continuity | `8b5be4b9a` |
| #1130 | One Business reading consent on every path | `cfaeba492` |
| #1132 | /biz locked polish | `bd6353a14` |
| #1123 | Guest first-open note and first-save sheet art slot | `1fb7fb141` |
| #1133 | Release Perfil without development leftovers | `5f72c8b9f` |
| #1138 | Search back half | `0f0b3073f` |
| #1134 | No empty heading, Spanish sidebar labels, separated Ajustes danger rows | `5ac5a0c6c` |
| #1141 | Worker reads consent through the canonical bridge (#1131 items 1, 3, 4) | `fad9bdd25` |
| #1144 | Web unit suite order-independent (#1135) | `79deb80b3` |
| #1142 | Accepted deletion relaunches signed out (option A, #1140) | `9954ff843` |
| #1147 | Perfil Idioma read-only row | `b89642f5c` |
| #1146 | UI tests refuse the legacy preview build | `164253afc` |
| #1150 | Accepted deletion removes only that account's local drafts (#1148) | `70a5c0b9c` |
| #1143 | Aprobar y siguiente on the receipt review page | `9a4c758b3` |
| #1153 | Registrar gasto sets up the paid-from account | `63d6f0135` |
| #1155 | DESIGN.md records the first-save sheet exception and the temporary hidden legal links | `e60a27b6c` |
| #1156 | Web legal links hidden until the Cuadrao pages publish | `dc849e1d9` |
| #1160 | iOS legal links hidden behind one owner, `CuadraoLegalURLs` | `e0a0706ad` |
| #1159 | Registrar gasto: approved account-setup copy and defaults, no duplicate account after a lost answer | `96f57c322` |
| #1161 | Undo notice on Search after delete or archive (decision 16) | `2b2665d63` |

## Open PRs from this sprint

Do not land any of these without a passing Eval at its current head.

| PR | Branch | Head | Eval state | Next step |
|---|---|---|---|---|
| #1158 Deletion analytics step not applicable when PostHog is unset (decision 1B) | `claude/deletion-analytics-not-applicable` | `a1aa541fe` | Conflicting verdicts at this head. One independent Eval passed it. The coordinator's Opus Eval failed it after reproducing a fail-open on real Postgres: an operator sweep or force run from an environment without the token marked a pending step not applicable and finished the deletion. Not reachable today (deletion off, staging has no token). | Finish the fix on the WIP branch `claude/deletion-analytics-first-pass-wip` (`49ae8cc55`, worktree `argus-worktrees/lane-del-1b`). Rule: only the API route's first pass may record not applicable; a pending step stays pending. Then a fresh Opus Eval. The founder has not yet chosen between landing `a1aa541fe` and waiting for the fix. |
| #1164 iOS sign-up acceptance sentence hidden until both Terms and Privacy are set | `claude/ios-signup-terms-hidden` | `f8fe1772d` | No Eval. Red on `e0a0706ad`, green at the head for the unit script (Debug and Release) and both sign-up UI tests. CI green at the head (7 pass, docs-checks skipped). Next for independent Eval. | Opus Eval at the head, because it touches consent text. Also take a both-set dark screenshot. `CuadraoCreateAccount.swift` is preview-only and was left alone (FOR LUCAS). With only one URL set, the sentence and its single link both hide. |
| #1163 Release checklist requires published legal links | `claude/release-legal-checklist` | `f84355b31` | Final head, stated in the PR body. Next for independent Eval. Touches `docs/specs/argus-execution-board.md` only. | Docs Eval. |

Older open PRs predate this sprint and were not touched: #1085 (kept open by decision 8), #1081, #1071, #1068, #927, #925, #896, #781, #732, #646.

## Work-in-progress branches

Work in flight at wind-down was committed as-is and pushed to its own branch. Each WIP commit message starts with `[WIP]` and says what is done, what is left and which tests ran. None of these may land.

| Branch | Head | Contents |
|---|---|---|
| `claude/business-approved-version` | `39608184b` | Lane a, described below. No PR yet. |
| `claude/deletion-analytics-first-pass-wip` | `49ae8cc55` | The #1158 fix: red tests `90ae195ec` and the `service.py` and doc edits. No tests were run after the edits. Move it onto #1158's branch when it is green. |
| `claude/sprint-map-review-ca3450` | `3d257373f` | The earlier October 15 checkpoint report, not reconciled with later landings. This handoff is newer. |

## Branches in flight without a PR

- **Lane a**, `claude/business-approved-version` at `39608184b`, worktree `argus-worktrees/lane-business-a`. The approval confirmation names the approved version with its date. After the last row it returns to the Bandeja's empty "todo revisado" state, and focus moves to the next heading. It closes #1154 once it lands. A reviewer found one P3 bug. The "focus the next heading" flag leaks to a later page when the next receipt fails to load, the dossier is unavailable, or the person leaves while loading. Fix: tie the handoff to the receipt id (`handTitleFocus(next)`, `takeTitleFocus(id)`), and pass `recordId` to `ReceiptReviewFrame`. Also remove the orphan locale key `business.inbox.empty_title`. Then open the PR and run an Opus Eval.

## Follow-ups

- **Legal URL variables.** Add `NEXT_PUBLIC_CUADRAO_TERMS_URL`, `NEXT_PUBLIC_CUADRAO_PRIVACY_URL` and `NEXT_PUBLIC_CUADRAO_DATA_DELETION_URL` to `render.yaml` (`sync: false`) and the web env examples. They are build-time values, so publishing needs a rebuild. Set both Terms and Privacy, because one alone shows nothing. Tracked in #1162.
- **Acceptance line returns before public signup and App Review**, on iOS and web: "Al continuar, aceptas los [Términos] y la [Política de privacidad]." / "By continuing, you agree to the [Terms] and [Privacy Policy].", both linked, no checkbox (founder, October 15). Tracked in #1162 and #1163.
- **`CuadraoLegalURLs.published`** must be filled with the published URLs before external TestFlight or App Review (#1163).
- **"Cuenta corriente" is cut off at 390px** in the Registrar gasto account-type picker. #1159 has landed, so this can start now.
- **Deletion runbook.** If PostHog events were ever sent, turn the deletion adapter on before deletion. Add the same no-token check for production before deletion is enabled there. Do this after #1158, because it is the same runbook.
- **iOS Profile.** The "links unavailable" line uses two different apostrophes ("aren't" and "aren’t"). Use one.
- **Decision 17** is recorded in DESIGN.md (#1155) but not yet in `docs/specs/argus-decision-log.md`.
- **Undo notice follow-ups** (#1165): move the GuestPlans contribution-delete toast to the shell's `offerUndo`, and rename the close id to `toast.close`.
- **Eval comments.** The independent Eval write-ups for #1156, #1159 and #1161 were not posted on their PRs, because the comment files were not on this machine.
- **Legacy consumer web** still hardcodes `/terms` and `/privacy` (`ProfileMenu`, `GuestLegalFooter`). Out of scope for now (#1162).

## Blocked, with the reason

- **Marketing legal pages PR.** Not started. It is waiting on the three cleared source files (`privacidad.md`, `terminos.md`, `eliminar-datos.md`), which are not in this repository or on this machine. Scope from the founder, October 15, all inside `marketing/` on its own branch:
  - Replace `privacy-copy.ts` with `/privacidad`. Add `/terminos` and `/eliminar-datos`, and link "Términos" in the footer. Strip every review comment and never publish `notes.md`.
  - Footer line: "¿Necesitas ayuda? Escríbenos a hola@cuadrao.ai".
  - Contact form: the WhatsApp option reads "Prefiero que Cuadrao me escriba por WhatsApp" / "I'd like Cuadrao to message me on WhatsApp". A number given there is used only to reply to that inquiry. "Quiero ver el prototipo y probarlo" stays unticked by default.
  - Waitlist emails carry "Dejar de recibir estos correos", which removes the person from the list.
  - A scheduled job deletes the email when someone leaves the list. It deletes all remaining waitlist emails 12 months after launch, with the launch date in config and empty until the founder sets it. Keep only the hash, and only for the re-add suppression check.
  - Set `CUADRAO_TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP` behind the Cloudflare proxy.
  - Staging: `cuadrao-web-staging` runs `web/` (the Business app), checked October 15. The marketing site therefore needs its own staging service on Render, staging only and with no production keys. Do not touch `cuadrao-web` or `cuadrao-api`.
  - Evidence: the staging URL, both forms tested end to end, and 390px screenshots of each page. Then an independent Eval at the exact head.
  - No production deploy and no DNS until the founder says yes.
  - WhatsApp sending is not in this PR. When it is built, the first outbound message is an approved template, free-form messages are allowed only within 24 hours of the person's last message, and "BAJA" stops all messages.
- **Lane c**, an export button on a Business screen, did not start. It waits for lane a to land and for the founder to choose the screen.
- **Lane e**, branded Spanish auth emails, waits for lanes a to c and for founder approval of the copy.
- **Account deletion release readiness.** Option A is landed. Readiness still needs #1158, a resume-sweep schedule and #805, plus #806 wherever PostHog events were sent. The deletion route is off on staging. The lost-response or 401 recovery case is a separate open gap.
- **Owner to accountant flow on staging.** Complete in code through export. The staging walk still needs a staging auth email sender (no SMTP, hook off), the accountant onboarding allowlist, the owner walk and accept-period approval.
- **Waiting on the founder:** decisions 2, 3, 4, 6 and 14. Confirm the narrower #806 gate wording in #1158. Choose whether to land #1158 at `a1aa541fe` or wait for the fix.
- **Waiting on product:** decisions 5 and 9 to 13. The interpretations landed in #1159 (the name follows the currency while untouched; "most-used" read as the majority account type) need product confirmation. Also the iOS account-setup mismatch, #1157.

## Working rules carried forward

- Land only with a passing Eval at the exact head, then squash with `--match-head-commit`. Check the tip's CI and the staging deploy after each landing.
- Never use Fable. Use Opus for Evals and for any money, auth, data or deletion work. The independent verifier runs on a fresh agent.
- iOS UI tests need the gitignored `ios/Config/Local.xcconfig`. Without it the app builds as the legacy preview. Use at most two simulators.
- Every UI brief cites the owning DESIGN.md (`.agent/designs/cuadrao/DESIGN.md` for iOS, `.agent/designs/argus/DESIGN.md` for /biz) and the approved decisions, and flags conflicts instead of guessing.
- Leave worktrees in place. The founder archives them.
