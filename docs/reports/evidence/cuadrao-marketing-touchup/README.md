# Cuadrao marketing touch-up review

## Scope and holds

This work moves the approved spacious touch-up into the maintained Next.js marketing app. Business, Personal, Contact and Privacy remain available in Spanish and English. Shared routes, form handlers, privacy text and consent logic remain the existing canonical implementations. No iframe or comparison-server dependency remains.

The new text is a draft for founder review in [copy-review.md](copy-review.md). No merge, publication, hosted migration, Render service, provider secret, real email or domain action is authorized by this report. Public forms and the operator section retain the LLC/operator hold. A local start without provider configuration reports unavailable and cannot send mail.

Original integration base: `bbf4da23f01296af4ac639386fe9a0960218a49f`. Branch: `codex/marketing-touchup-delivery`.

## Reference decisions

Both founder-provided recordings were inspected directly, frame by frame:

- Granola, recording `2026-10-09 at 12.41.17 AM`: a shallow image band under the oversized cropped footer wordmark. Adapted as a bounded 200 px desktop / 150 px mobile ending, not another full-screen section.
- YC, recording `2026-10-09 at 12.44.04 AM`: thin moving grid lines, corner squares, cropped type. Adapted to Cuadrao pine, sage and lime. No reference logos or footage are reused.

The footer starts moving when visible, pauses off screen, has an explicit pause control, and remains static with reduced motion. Its bottom border is the actual page ending. The original footer navigation and wordmark composition remain.

The original hero card behavior is a 2 degree resting rotation to 1 degree on hover over 220 ms. The maintained touch-up uses that same behavior; there was no separate shake keyframe in the source.

The document journey uses a keyboard-operable three-tab progress rail. The pilot sequence remains an ordered list with a connecting rail. Numerical prefixes are removed.

## Asset provenance

- Header lockup: canonical `marketing/brand/cuadrao-lockup-light.svg`. `marketing/scripts/sync-brand.mjs` derives the served copy during dev/build.
- Florist and accountant images: founder-provided illustrative images, recovered from the prior approved touch-up assets, already optimized as WebP. The page labels them as AI illustrations, not customers.
- Business product image: actual local synthetic Business capture. Exact runtime and image details are recorded with the final evidence below.
- Founder portrait, signature, Personal screen and footer artwork retain the canonical existing assets.

## Reproduction

From `marketing/`, install the pinned lockfile with `bun install --frozen-lockfile`.

```sh
bun run test
bun run typecheck
bun run lint
bun run build
CI=1 MARKETING_E2E_SITE_PORT=4540 MARKETING_E2E_PUBLIC_PORT=4541 MARKETING_E2E_MOCK_PORT=4542 bun run test:e2e
bun run start --hostname 127.0.0.1 -p 4512
```

The browser suite supplies mock provider configuration and synthetic addresses. It covers validation, success, unavailable and retry states without sending real messages. The environment-variable overrides isolate its three servers from the founder's comparison and Business servers. Default CI ports are unchanged.

The comparison page on 4511 is a separate preserved snapshot. The touch-up does not fetch any assets or content from it.

## Verification record

Pending final exact-commit checks and screenshots. Interim: 177 unit tests, typecheck, lint and production build pass. Existing 130 browser tests pass. The initial two new footer tests had a changing locator after clicking Pause; correcting that test yielded 6/6 focused desktop/mobile header, footer and reduced-motion checks. The missing product capture was deliberately kept as an open item rather than replaced with a fabricated screen.

### Actual Business image

The Business runtime owner captured `business-inbox-source.png` and `business-review-source.png` at 1440×1000 from the running local `/biz` app on October 9, 2026, checkout head `d136c3394`. It used a separate synthetic account, Spanish profile and an actual saved fixture upload (`receipt-dop.png`). AI preparation was off. The review form is intentionally unfilled and the receipt is not claimed to be an approved expense. No DOM text was replaced and no owner account was changed. The served image is a browser viewport clip of the receipt/review area so the product stays readable and development chrome stays outside the frame.
