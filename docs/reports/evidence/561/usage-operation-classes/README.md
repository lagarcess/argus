# PR #561: usage allowances keyed by operation class

Browser evidence for the user-visible half of the Metering board item: the
Usage dialog now shows three operation classes. Conversation and, for a
signed-in account while the research rail is on, searches with sources are
unbounded and render as a plain "No limit" row; simulations keep the gauge.

| File | Account | Language | Theme | Stubbed `/me/usage` |
| --- | --- | --- | --- | --- |
| `en-light-registered.png` | registered | en | light | compute and grounding unbounded; execution 1/10 this hour, 4/50 today, `limiting_window: "hour"` |
| `es-419-dark-registered.png` | registered | es-419 | dark | same allowances |

Captured by `web/e2e/usage-allowance.spec.ts` ("Usage keys allowances by
operation class in ...") with `ARGUS_CAPTURE_USAGE_CLASSES_EVIDENCE=1`,
against the Next dev server with `/api/v1/me` and `/api/v1/me/usage` stubbed
by the spec. The modal source (`web/components/settings/UsageModal.tsx`) and
both locale catalogs are identical between the capture and the commit that
adds these files; only the spec and this folder were added afterwards.

Not captured here: the guest workspace line ("0 left in this temporary chat ·
expires ...") that appears when `execution.limiting_window` is
`guest_session`. The mocked shell has no guest bootstrap, so a stubbed guest
account lands on the sign-in page instead of the chat shell. That path is
covered by `tests/test_usage_allowance_classes.py` (backend truth for all five
guest bound combinations), `web/__tests__/guest-capability-gates.test.ts`
(the reset horizon the conversion prompt receives), and the source pins in
`web/__tests__/usage-allowance.test.ts`.
