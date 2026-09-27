# Approved mobile design baseline · 2026-09-27

This folder publishes files that already existed. It does not restate their decisions. Read the copied files.

Mobile is the design baseline. Desktop and tablet layout stay open. Publishing this bundle does not implement product code, schema, financial behavior, or a deployment.

The sketch notes mention a preview server on the founder's machine. Do not assume that server, or any `127.0.0.1` address, is reachable. Read the files in this folder.

## Files

| Path | What it is |
| --- | --- |
| [sketch/APPROVED-BASELINE.md](sketch/APPROVED-BASELINE.md) | The accepted visual and interaction record, including what stays open. |
| [sketch/INHERITANCE.md](sketch/INHERITANCE.md) | The inheritance and iteration record. Later explicit refinements in that file supersede earlier experiments. |
| [sketch/](sketch/) | The runnable sketch: HTML, CSS, JS, fonts, and licenses. `sketch/index.html` is the entry. `sketch/typography.html` is an earlier exploration, not this baseline. |
| [evidence/](evidence/) | The three screenshots stored with the approved checkpoint. |
| [checkpoint/SHA256SUMS](checkpoint/SHA256SUMS) | Checksums for the approved archive payload. The `sketch/` and `evidence/` copies match those lines. |
| [checkpoint/argus-sketch-20260927-005113-approved-baseline.zip](checkpoint/argus-sketch-20260927-005113-approved-baseline.zip) | The approved archive. SHA-256 `c1df28ca112026752bb994a1579fb6b564f50ad41522545142f8357362ee3d45`. |
| [checkpoint/README.md](checkpoint/README.md) | The archive note, copied unchanged. Its server command is not a reachable endpoint. |
| [checkpoint/superseded/](checkpoint/superseded/) | The earlier 2026-09-26 23:37 zip. Not the baseline. |

`sketch/fonts/` matches `web/app/fonts` byte for byte. `web/app/fonts` remains the production font owner.

## Native interface stacks

The sketch files do not contain a native-stack decision. A written decision does exist in this repository: founder commit `173400e1cb5a8a35ec81363653deffadf0ed809b`, message `docs(architecture): lock native mobile interface stacks`. This change republishes that commit's text unchanged. The owner is [ARCHITECTURE.md — Approved Platform Direction](../../ARCHITECTURE.md#approved-platform-direction). Do not treat this README as a second copy.
