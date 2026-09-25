# Argus Decision Log

This log records locked product decisions. Product decisions are added here
after they travel from Product through Head of Engineering to Docs.

## Locked

| Date | Decision | Locked by |
| --- | --- | --- |
| 2026-09-14 | Sharing is shareable by default; refuse only what is private. The privacy boundary is owner selection of turns, an exact preview, and no Argus ids or account enrichment. Earlier refusals for memory use, degraded answers, missing sources, unlisted URLs, credential-shape and value-marker scanning, and length caps were removed in [#632](https://github.com/lagarcess/argus/pull/632) (commit `6054acba`, merge `c8e05b4f`). That reversed the 2026-09-09 filter built in [#574](https://github.com/lagarcess/argus/pull/574) after [#604](https://github.com/lagarcess/argus/issues/604), whose promotion walk found zero selectable answers. A Codex P1 review comment on #632 asking to restore value-marker scanning was declined because it would re-block public company names and URLs. See [conversation-sharing.md](conversation-sharing.md). | Lucas |
| 2026-09-14 | Receiver fork: a person who opens a shared `/r/<id>` link and sends a follow-up gets the frozen shared turns copied into their own new chat. The copy carries no owner note, memory, or profile. Decision commit `675c1f94` reversed the earlier no-fork stance. Built in [#643](https://github.com/lagarcess/argus/pull/643), merged at `0044d79a` on 2026-09-15. See [conversation-sharing.md](conversation-sharing.md). | Lucas |
| 2026-09-24 | The first user is people living in the Dominican Republic, not the diaspora. | Lucas |
| 2026-09-24 | Argus keeps all its existing grounded chat and calculation capability. The pivot adds features around it so Argus isn't just an AI chat, building toward an ecosystem. | Lucas |
| 2026-09-25 | Lucas locked the three-step setup checklist: get a first answer; save a card or create a goal, which is where sign-in happens; then turn on reminders. | Lucas |

## Open (not locked)

Wave 1 roadmap drafted 2026-09-25, awaiting Lucas approval. See
[argus-wave-1-roadmap.md](argus-wave-1-roadmap.md). Status: open/draft.

Whether existing Argus and the pivot become one product or two. Likely one, but Lucas has not confirmed.
