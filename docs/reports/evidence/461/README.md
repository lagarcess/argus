# Issue #461 access welcome evidence

Status: preliminary exact-source evidence. Final-candidate CI is still required for the new real-gateway double-promotion proof.

## Candidate identity

- Integration base: `80256729`.
- First Task 5 evidence commit and initial CI target: `41d189285b18a864d1749cea0a3203cfdf374264`.
- This proof-tightening working tree is based on `41d18928`; its successor exact-head CI target remains pending until this fix is committed.
- Email implementation and code-owned HTML source head: `30f2830cad5ce08315c421289252bb7203d4afae`.
- Branch: `codex/issue-461-welcome-email`.
- Content version: `private-alpha-access-welcome/v1`.
- No hosted migration, production deploy, live canary, hosted application API call, or real application SMTP call occurred in Task 5.

## Deterministic verification

All commands ran from the issue branch working tree on 2026-08-12.

| Command | Result |
| --- | --- |
| `poetry run python -V` | Python 3.10.20 |
| Focused nine-file pytest matrix from the Task 5 brief | 214 passed, 19 skipped, 233 collected |
| Focused real-gateway proof only | 1 collected, 1 skipped because the disposable local Supabase gateway environment is absent |
| Task 5 Ruff command | Passed, no findings |
| Task 5 mypy command | Passed, no issues in 2 source files |
| `poetry run python scripts/check_modularity_budget.py` | Passed, no watched-file budget violations |
| `bash -n .github/canary-render.sh` | Passed |
| Shell and release-doc pytest matrix | 112 passed |
| OpenAPI compatibility matrix | 23 passed; no generated drift, so the generator was not run and `docs/api/openapi.yaml` was not changed |
| `shellcheck .github/canary-render.sh` | Not run because shellcheck is unavailable locally |

The 19 focused skips are the real-PostgreSQL access-request file. Local Docker is unavailable, `supabase/config.toml` names the shared `argus-qa` project, and the required disposable Supabase variables are absent. The shared project was not started, reset, or mutated.

## Proportional backend sweep

`poetry run pytest tests -q --no-cov` collected 5,561 tests and ended with 5,044 passed, 509 skipped, and 8 failed.

Seven failures were reproduced at untouched base `80256729`:

- one process-tree RSS probe was denied by the macOS sandbox;
- five local HTTP stub tests were denied permission to bind a loopback socket;
- one OpenRouter traceback-origin test reported `<unknown>` at both base and candidate.

An allowed out-of-sandbox rerun made the RSS probe and all five loopback tests pass. The OpenRouter traceback-origin failure remained and is baseline-reproduced.

The eighth failure was candidate-specific but outside Task 5 ownership: `tests/test_render_canary_script.py` grew to 1,042 lines and crossed the 1,000-line modularity watch threshold without being listed in `.agent/modularity_budget.json`. Commit `b4b4c747` added the file to the watched budget. The exact failing structural test now passes. The release captain directed against repeating the broad local sweep; exact-head CI remains the terminal truth.

## Browser rendering proof

The screenshots are generated from `build_access_welcome_email` at source head `30f2830c`, using `https://argus.example/?auth=signup` as a non-production origin. The temporary EN and `es-419` files were the exact, unmodified builder HTML bytes. The server supplied `Content-Type: text/html; charset=utf-8`; the fixed viewport was set only through Playwright. No wrapper, `<head>`, `<meta>`, product copy, or style was added to the document.

Before capture, the served response bodies compared byte-for-byte equal to the generated builder files. The exact screenshot-source HTML hashes were:

- EN: `05cfb6b657d2e7b7c7ff2c2d239f5d9e3bc62875230db46622951f308c692226`.
- `es-419`: `94d173aab4c75cc922b1cad9f2fd39697c0ef49f984460d038f59895e6e78ee4`.

Final Playwright captures used separate fresh contexts at the same fixed `602 x 900` mobile-friendly viewport. Each context explicitly reset horizontal and vertical scroll to zero. For both languages:

- `document.characterSet` was `UTF-8`;
- `document.head.innerHTML` was empty;
- `scrollWidth` equaled the 602px viewport width;
- the 560px email table occupied integer coordinates `x=21` through `x=581`;
- the full CTA, fallback link, and support line were inside the capture;
- the CTA target was `https://argus.example/?auth=signup`;
- the computed CTA background was `rgb(25, 28, 31)` and radius was `9999px`.

| Evidence | SHA-256 | Inspection |
| --- | --- | --- |
| `welcome-email-en.png` | `6ece87cae32ab226b047274ecd89cbbb7c447b12c6070d88779ea79999937e13` | Full English copy, button, link, and support line visible |
| `welcome-email-es-419.png` | `fd5a39da5d8270507fabc1742a23b225fa471eced183a03b5e5ce93e835c6fa0` | Full Spanish copy and accents visible, including `inversión`, `histórica`, `botón`, and `¿Tienes` |

The first Spanish capture was rejected because the temporary server did not declare UTF-8 and rendered mojibake. A later 430px capture also clipped the 560px email canvas. The English capture retained stale horizontal state during one retry. All rejected frames were overwritten. The final frames above serve exact builder bytes with UTF-8 supplied only by HTTP, use an integer-centered canvas and fresh zero-scroll contexts, and add nothing to the document. Standalone image inspection confirmed both corrected PNGs.

## External delivery proof

The release captain generated the exact English content from source head `30f2830c` and derived the signup link from the existing configured application URL. The credential-owning Resend connector accepted exactly one message from address-form `noreply@get-argus.com` with subject `Welcome to Argus`. An earlier `Argus <noreply@get-argus.com>` connector input was rejected by connector schema before submission and sent nothing. External display-name proof is therefore unproven.

Fresh sanitized Gmail RAW evidence in `raw-header-proof.txt` confirms SPF, DKIM, and DMARC pass plus `multipart/alternative`, with `text/plain; charset=utf-8` and `text/html; charset=utf-8` child parts. The matching message was in Inbox, excluded Spam and Trash, and had no Spam match.

The release captain compared both decoded Gmail MIME parts to builder output generated with that configured signup URL:

- builder plain SHA-256: `4185d5cfdf2075302f65f27ae1be57280e6a0736acdba85771d256e57f0ec742`;
- decoded Gmail plain SHA-256 after CRLF-to-LF canonicalization: the same hash, equality true;
- builder HTML SHA-256: `5454c6625dc8ca74e6d73f29b2acb18b23c9f7d4a4b68c45e4d458002bea7316`;
- decoded Gmail HTML SHA-256: the same hash, byte equality true.

Plain-text canonicalization removed transport CRLF differences only. It did not change content.

This is connector-owned external delivery proof. It does not claim that the connector executed `send_access_welcome_email` or the hosted application's SMTP path. Deterministic production SMTP tests separately prove that the code emits `Argus <noreply@get-argus.com>` and preserves its multipart, idempotency-key, and acceptance behavior.

## Pending proof and release boundaries

- `idempotency-proof.txt` remains explicitly pending final-candidate, non-skipped CI for the new real-PostgreSQL plus real local Supabase gateway/TestClient test.
- Hosted migration application, hosted deployment, live canary, and production application SMTP execution remain unproven and did not occur in this task.
- No recipient address, credential, ops token, provider key, raw message body, or unredacted Message-ID is retained here.
