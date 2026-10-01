# Household Home and People separation — September 30, 2026

Founder approved keeping shared finances on Home and invitation administration
inside Personas / People. The empty Household uses one stable heading and financial
explanation across membership states, with Añadir cuenta conjunta as its primary
action. Before an invitation exists, Invitar a alguien is a quiet text shortcut.
Once a link or member exists, that shortcut reads Personas. Populated Household
uses the same Personas label. No badges, waiting card or repeat invitation prompt.

Personas contains the existing member and invitation UI, including sharing again,
cancellation and the recipient preview. Sharing, acceptance, privacy boundaries
and financial behavior are unchanged. English labels accompany the Spanish copy.

Verification: native build succeeded without reported warnings/errors; log
`build_run_sim_2026-10-01T00-21-52-934Z_pid12375_808c8122.log` (UTC filename).
Spanish simulator journey: create Household, inspect empty Home, prepare share
link, dismiss native sharing without sending, close Personas, inspect Home with
no invitation card, reopen Personas and confirm share/cancel/recipient controls.
Screenshots retained here. git diff --check passed. This small presentation change
was not given a new backend or broad device test matrix.

Reused the existing simulator and build cache. No messages, backend changes,
deployment or remote publication.
