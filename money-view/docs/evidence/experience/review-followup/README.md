# PR 664 review corrections

Base for this scoped delta: `ae9db555aab7da54202e507c60ce2e5f8745dc35`.
That head passed 700 backend and 61 browser tests in both private CI runs.
The review identified two reachable P2 findings, now corrected locally:

- [Conversation authority](https://github.com/lagarcess/argus/pull/664#discussion_r4079632835):
  remove the viewer exception from the existing shared transactional guard at
  conversation create/update, turn admission/replay and checkpoint/settlement.
  Viewer GET/list/export access remains; editor writes remain. Regression tests
  failed before the correction and now cover all mutation shapes, read/export,
  no durable side effects and internal checkpoint/settlement authority.
- [Guest settings](https://github.com/lagarcess/argus/pull/664#discussion_r4079632838):
  derive password capability from identity's guest state; share the guest schema
  between shell and settings. Hide unsupported password operations, retain
  export/reset, and explain guest session closure. After claim, the same panels
  regain their password controls.

Verification: 78 chat tests, 63 identity/guest tests, Ruff, and frontend build
pass. Two real local browser journeys cover EN/ES guest security, data controls,
session-closure copy and transition through claim. Both pass in 8.5 seconds.
Spanish security was visually inspected at 390px. Browser/model-provider keys
were blank; no live model or external vendor was used.

The source manifest fingerprints the corrected tree. These changes supersede
prior permission and guest-settings evidence only. Final CI and the review
scoped to these fixes must complete before private merge; the terminal PR audit
records their actual outcome. No claim of clean re-review is made here.
