# Web composition refinement

The previous READY claim is withdrawn. This checkpoint compares the preview
with the existing Argus web application and records a bounded refinement in
the same PR. It is not founder visual acceptance or landing authorization.

## Before and web references

The [reference run](before/run.txt) passed all nine cells and captured 31 PNGs
at code/harness head `2da77b1a09769901b9ca9bfe28d317eddde2ffa1`. Each cell's JSON
records source hashes, environment, requests and capture identity. All nine
record zero network violations, page exceptions and console errors.

| Surface | Existing web | Preview before refinement |
| --- | --- | --- |
| Desktop starting chat | [Production source](before/production-source-1440-cold-chat-expanded-rail.png), [integration](before/integration-1440-cold-chat-expanded-rail.png) | [Preview](before/preview-before-1440-argus.png) |
| Tablet navigation | [Expanded](before/integration-834-cold-chat-expanded-rail.png), [collapsed](before/integration-834-cold-chat-collapsed-rail.png) | [Preview](before/preview-before-834-argus.png) |
| Desktop active chat | [Production source](before/production-source-1440-active-chat-fixture.png), [integration](before/integration-1440-active-chat-fixture.png) | Historical sample-chat proof remains in the [original evidence index](../README.md) |
| Desktop settings | [Existing web](before/integration-1440-settings-open.png) | [Preview](before/preview-before-1440-settings.png) |
| Home composition | New ecosystem surface; use web shell and density, mobile content hierarchy | [Desktop](before/preview-before-1440-home.png), [tablet](before/preview-before-834-home.png), [narrow](before/preview-before-390-home.png) |
| Narrow chat/settings | [Chat](before/integration-390-cold-chat.png), [settings](before/integration-390-settings-open.png) | [Chat](before/preview-before-390-argus.png), [settings](before/preview-before-390-settings.png) |

Production-source identity: `a9286b21886eb03df7a21f2f4b7d5e79af570679` from an
isolated temporary source extraction. Integration identity:
`c3b2042b9b69c5b75e173d145ed0020f00ccd79e`. Named rendered source owners are
byte-verified against those Git objects. The full source web tree is recorded
for context, not claimed as a live deployment verification.

Both reference apps run with mock authentication and browser-fulfilled API
fixtures. They do not establish authorization or server persistence. All
unrecognized API/external traffic is rejected before transmission. Only local
Next.js development HMR sockets are allowed; an initial attempt that blocked
those sockets could not hydrate the webpack reference and was corrected before
this accepted run. No model turn, provider request or real financial write ran.

The reference harness freezes animations/caret and hides development-only
chrome through the repository's existing `FREEZE_CSS`. The preview's visible
sample disclosures remain. Captures use Chromium, 1440/834/390 × 1000, English,
Light, reduced motion and the America/Santo_Domingo timezone. Broader language,
theme, text-size and interaction acceptance belongs to the after run.

The [inheritance map](../../../ecosystem-web-preview.md#web-inheritance-checkpoint)
and [spec refinement](../../../../superpowers/specs/2026-09-28-responsive-ecosystem-preview.md#september-28-refinement-checkpoint)
define the changes. Earlier screenshots remain unchanged as historical evidence.
