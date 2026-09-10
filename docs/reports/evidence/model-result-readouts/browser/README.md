# Provider-free browser transport replay

This is browser transport and rendering evidence, **not model-quality evidence,
not a fresh backtest, and not the founder's DOCN comparison**. The screenshots
show fixture titles to make that distinction visible.

`proof.json` records exact candidate commit
`55e63bf7647eb8a6f87e152a05db3fb871a76594`, a clean runtime working tree, source
hashes, exact visible/copied text, API requests, and checks. All screenshots and
snapshots were recaptured after that implementation commit. Source hashes alone
do not replace the committed screenshots.

## Fixture provenance

- The old English META result message, card, stored figures, and chart come from
  `docs/reports/evidence/411/browser/en-discovery-messages.json`, result message
  `b215f293-81d5-427c-ae11-e0cab659f63e`. The source SHA-256 is
  `715adc440ad4fe1f4a109ee1cc2cb00b6bead70d596df1c8b6086d6dcd33963e`.
- `docs/reports/evidence/531/browser/replay_api.py` supplied the memory-replay
  approach. No hosted conversation or run is read or changed.
- Every `result_readout/v1` envelope in this replay is **synthetic**, manually
  composed in `replay_api.py` from that stored META result. This tests new-envelope
  display and transport only; it does not exercise model generation or grounding.
- Every Breakdown message is **synthetic**, including the legacy Breakdown.
  The legacy Breakdown uses the genuine saved run's typed fact bank and no new
  envelope. No genuine saved Breakdown row was found in the narrow evidence
  lookup. Thus the genuine pre-lane Quick take/card has browser proof, while the
  pre-lane Breakdown metadata shape has fixture proof.
- Conversation IDs are local aliases. The replay does not rewrite the committed
  source or saved product history.

## Checks and evidence

Browser plugin was not available. Repository Playwright/Chromium was used after
inspecting the controls through the Playwright CLI. Desktop: 1440×1050. Mobile:
390×844. The complete passing run recorded zero console warnings, zero console
errors, zero page errors, zero external browser requests, zero backend external
network attempts, and zero generation requests.

| State | Expected frame bodies | Evidence |
| --- | --- | --- |
| New English envelope, English workspace | Complete supplied English text | `new-en-match.png` |
| New English envelope, Spanish workspace | Spanish templates | `new-en-mismatch-es.png` |
| Same mismatch after reload | Same Spanish templates | `new-en-mismatch-es-reload.aria.txt` |
| New Spanish envelope, Spanish workspace | Complete supplied Spanish text | `new-es-match.png` |
| New Spanish envelope, English workspace | English templates | `new-es-mismatch-en.png` |
| Same mismatch after reload | Same English templates | `new-es-mismatch-en-reload.aria.txt` |
| Pre-lane result, English workspace | English templates | `legacy-en.png` |
| Pre-lane result, Spanish workspace | Spanish templates | `legacy-es.png` |
| Same old result after reload | Same Spanish templates | `legacy-es-reload.aria.txt` |

Both frames keep their labels and order. Exactly one result card remains. The
card is also captured separately in `new-en-result-card.png`. The Spanish mobile
captures show both the Quick take and the lower, scroll-reachable Breakdown:
`new-es-mobile-quick-take.png`, `new-es-mobile-breakdown.png`. No horizontal page
overflow was detected.

The API was restarted against the committed candidate. Its loaded reader-source
hashes match the source hashes recorded by the browser runner. The seeded raw
messages' digest is unchanged after all reads, Settings switches, and reloads.

Settings switches were exercised through the actual UI, then verified after
reload. For each of the nine states, the real clipboard handler was exercised
through More Actions and keyboard activation of Copy Plain Text / Copiar texto.
Result-message copy preserves the card and includes the exact displayed Quick
take. Breakdown copy equals its displayed body. Mismatch templates and legacy
templates are identical in the same workspace language. Private source text and
the synthetic private Breakdown sentinel do not appear in either frame.

The existing historical-message toolbar appears on hover. Keyboard activation
was used because a following message can overlap that older message's copy menu
pointer target. No application change was made for that pre-existing interaction.
The existing sidebar's expand control has the English accessible label
`Expand sidebar` in both languages; readout frame labels are localized.

## Reproduce locally

Run each server from the repository root in a separate terminal:

```sh
.venv/bin/python docs/reports/evidence/model-result-readouts/browser/replay_api.py
.venv/bin/python docs/reports/evidence/model-result-readouts/browser/start_web.py
node docs/reports/evidence/model-result-readouts/browser/capture.cjs
```

The API is `http://127.0.0.1:8539`; the frontend is
`http://127.0.0.1:3219`. The API disables dotenv and inherited credentials before
Argus imports, uses memory persistence and mock auth, rejects chat/backtest
generation POSTs, and throws on non-loopback DNS/socket connections. The browser
blocks non-loopback requests before navigation. The web launcher overrides
dotenv variables without printing their values and uses
`NEXT_DIST_DIR=.next-readout-replay`. No environment file is written. Next may
automatically add its isolated output directory to `web/tsconfig.json`; restore
only those generated changes after startup. Do not commit `.next-readout-replay`.

The runner resets the local mock user's language to English before each run.
The three measured language switches use Settings and PATCH only that local
memory profile. `/replay-proof` exposes the no-generation counters and fixture
provenance.

Open `/chat?conversation=` with these aliases:

| Case | Conversation alias |
| --- | --- |
| Old result | `00000000-0000-4000-8000-000000005391` |
| Synthetic new English envelope | `00000000-0000-4000-8000-000000005392` |
| Synthetic new Spanish envelope | `00000000-0000-4000-8000-000000005393` |

## Founder DOCN side-by-side steps for the real PR preview

Use the PR's real preview link, **not the provider-free replay above**, which
deliberately rejects generation. Both comparisons must use the same date window,
starting capital, benchmark, and cost assumptions. These are reproduction steps;
this replay did not execute DOCN or measure the model's text.

1. English: expand the sidebar, open **Settings → Preferences → App language →
   English**, then **New chat**. Send: `buy and hold DOCN since September 2023
   against SPY`.
2. If the setup asks for dates or capital, supply: `Start September 1, 2023,
   end September 9, 2026, with $10,000 starting capital. Use SPY as the benchmark.`
   Use the same explicit window for the competitor comparison. Review the
   confirmation's effective window and cost assumptions, then choose
   **Run backtest**.
3. Compare the **Quick take** with the card. Choose **Explain result** to open
   **Breakdown**. Record whether it adds a meaningful explanation of comparison,
   roughness, and drawdown scale rather than only repeating the card. These
   model-quality judgments require the separate approved live evidence.
4. Spanish: **Ajustes → Preferencias → Idioma de la app → Español**, then
   **Nuevo chat**. Send: `Compra y mantén DOCN desde septiembre de 2023 y compáralo
   con SPY`.
5. If needed, supply: `Del 1 de septiembre de 2023 al 9 de septiembre de 2026,
   con un capital inicial de $10,000. Usa SPY como referencia.` Review the same
   assumptions and choose **Ejecutar backtest**, then compare **Lectura rápida**
   and **Explicar resultado → Desglose**.
6. Switch each saved result to the other workspace language and reload. Both
   frames should use localized templates. Switching back restores its stored
   composition-language text without regenerating or rewriting it.

Settings, readout frame, and copy labels were observed in browser. Confirmation
and Explain result labels were checked against the current locale catalogs; the
replay already contains a Breakdown, so it does not click the generation action.
