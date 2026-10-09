# Cuadrao marketing touch-up review

## Scope and holds

This work moves the proposed spacious touch-up into the maintained Next.js marketing app. The founder has not accepted the current design. Passing tests do not establish design approval. The current ownership and resume point are in the [Marketing handoff](../../../handoffs/cuadrao-marketing-launch-lane.md). Business, Personal, Contact and Privacy remain available in Spanish and English. Shared routes, form handlers, privacy text and consent logic remain the existing canonical implementations. No iframe or comparison-server dependency remains.

The new text is a draft for founder review in [copy-review.md](copy-review.md). No merge, publication, hosted migration, Render service, provider secret, real email or domain action is authorized by this report. Public forms and the operator section retain the LLC/operator hold. A local start without provider configuration reports unavailable and cannot send mail.

Original integration base: `bbf4da23f01296af4ac639386fe9a0960218a49f`. Branch: `codex/marketing-touchup-delivery`.

## Founder correction, 2026-10-09

The founder requested removal of the incomplete Business product screenshot because its numbers were incorrect. The Marketing page no longer renders that section in either language. Its localized copy, unused styles, and served `business-review.webp` asset are removed. Historical evidence images remain here for traceability.

The earlier screenshots and browser results below describe the previous page. They do not verify this removal or establish design approval. The removal passes TypeScript, lint, and 40 focused unit tests covering existing sample money, priorities, and routes. The rebuilt page passes all 20 focused browser checks on desktop and mobile. That removal left header and footer behavior unchanged. The separate footer correction below supersedes the previous motion design.

## Footer correction, 2026-10-09

The founder confirmed that footer photos must be fully hidden at rest. The natural page ending remains the existing cropped hollow Cuadrao wordmark. Extra downward wheel or touch input at the page bottom briefly reveals a bounded photo strip; stopping input returns it to the crop. There is no added scroll height, autoplay, moving grid, pause button, scroll lock, or forced scroll correction. Upward scrolling and keyboard navigation remain native. Reduced motion keeps the static crop.

The implementation uses one reveal offset on a clipped track containing the existing wordmark and an absolutely positioned photo strip. The reveal is bounded by both the rendered strip height and 60% of the cropped frame height, so the peek stays shallow on phones. Native overscroll alone was rejected because it cannot consistently expose custom clipped photos across browsers.

The founder supplied replacement footer photos during this correction. The dressmaker appears on the left and the artisan on the right. Original files are copied unchanged; Next/Image owns responsive delivery, and CSS crops toward the upper body without stretching. Final crop review, visual acceptance, and header direction are pending. The main editorial florist/accountant images remain unchanged.

Typecheck, lint, and a fresh production build pass. All 20 focused browser checks pass on desktop and mobile. They cover resting crop, wheel peek, idle return, fixed document height, upward wheel departure, keyboard navigation, reduced motion, both languages, and dispatched touch drag/release. The first run caught the hidden photos remaining unloaded because they were lazy-loaded. Both footer images now load eagerly through the existing Next.js image optimizer; the rerun passes. Dispatched touch events test the handler; they do not prove physical iPhone overscroll behavior. The release captain reviewed the bounded diff and verified the rebuilt preview. No founder design acceptance, new GitHub CI verdict, or release readiness is claimed.

`marketing/scripts/capture-touchup.mjs` now writes to `footer-peek-screens/` and captures rest, peek, and settled states. It preserves the historical `screens/` images and manifest. Existing screenshot and test evidence below does not validate this correction.

## Historical reference decisions

Both founder-provided recordings were inspected directly, frame by frame:

- Granola, recording `2026-10-09 at 12.41.17 AM`: a shallow image band under the oversized cropped footer wordmark. Adapted as a bounded 200 px desktop / 150 px mobile ending, not another full-screen section.
- YC, recording `2026-10-09 at 12.44.04 AM`: thin moving grid lines, corner squares, cropped type. Adapted to Cuadrao pine, sage and lime. No reference logos or footage are reused.

The previous footer started moving when visible, paused off screen, and had an explicit pause control. That design is superseded by the founder correction above. Its historical evidence remains below.

The original hero card behavior is a 2 degree resting rotation to 1 degree on hover over 220 ms. The maintained touch-up uses that same behavior; there was no separate shake keyframe in the source.

The document journey uses a keyboard-operable three-tab progress rail. The pilot sequence remains an ordered list with a connecting rail. Numerical prefixes are removed.

## Asset provenance

- Header lockup: canonical `marketing/brand/cuadrao-lockup-light.svg`. `marketing/scripts/sync-brand.mjs` derives the served copy during dev/build.
- Florist and accountant images: founder-provided illustrative images, recovered from the prior approved touch-up assets, already optimized as WebP. The page labels them as AI illustrations, not customers.
- Footer dressmaker: founder-supplied `codex-clipboard-123a87f8-93d2-4fef-be87-24e3c1fa6ed2.png`, copied unchanged to `marketing/public/cuadrao-site/footer-dressmaker.png` (1456×1360).
- Footer artisan: founder-supplied `grok-image-064f7fef-226b-4166-92db-7e8aa4579b64.jpg`, copied unchanged to `marketing/public/cuadrao-site/footer-artisan.jpg` (1728×1152). Neither image is asserted to depict a customer.
- Withdrawn Business product image: historical local synthetic capture, removed at the founder's request. The source evidence below remains for traceability.
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

Implementation commit: `85c8cdf2a17c4a8dc6ff2990b75d6d44451cc40e`. Test-only pause synchronization: `fc1c3a0c40aae17075228674f330ef3a10d7170c`.

- 177 unit tests pass; typecheck, lint and fresh production build pass.
- Final complete browser matrix: **142/142 pass**, desktop 1440 px and touch/mobile 390 px, plus all routes at 320 px with reduced motion. Includes form validation, mock success, unavailable/retry, canonical routes, keyboard navigation, image loading and automated WCAG 2.1 AA checks.
- Footer pause repeated three times per desktop/mobile: **6/6 pass**. The initial test measured before React applied the pause and saw one frame of movement; the final assertion waits for the rendered paused state and still verifies a fixed position.
- Independent focused code/UI review and final delta review: **clean, no actionable findings**. No unchanged runtime was opened for speculative work.
- Modularity budget: no violations. Integration remained `bbf4da23f01296af4ac639386fe9a0960218a49f`; no reconciliation merge or semantic overlap was needed.
- [Screenshot manifest](screens/manifest.json) pins the actual product implementation commit and capture time. The later commit changes only test synchronization; product source is identical, so these images described that earlier revision. The Business page images are now historical after the removal above. The final evidence commit changes documentation/images only.
- [Desktop Business](screens/business-es.png), [390 px Business](screens/business-es-390.png), [320 px Business](screens/business-es-320.png), [Personal](screens/personal-es.png), [Contact](screens/contact-es.png), [Privacy](screens/privacy-es.png). Matching English images are in the same directory.
- [Footer first frame](screens/footer-motion-start.png), [later frame](screens/footer-motion-later.png), [paused state](screens/footer-paused.png).

Hosted checks and publication are not part of this local acceptance. GitHub CI and founder copy approval remain separate gates.

### Withdrawn Business image provenance

The Business runtime owner captured `business-inbox-source.png` and `business-review-source.png` at 1440×1000 from the running local `/biz` app on October 9, 2026, checkout head `d136c3394`. It used a separate synthetic account, Spanish profile and an actual saved fixture upload (`receipt-dop.png`). AI preparation was off. The review form is intentionally unfilled and the receipt is not claimed to be an approved expense. No DOM text was replaced and no owner account was changed. The former served image was a browser viewport clip of the receipt/review area so the product stays readable and development chrome stays outside the frame.

The focused browser log is [footer-peek-results.txt](footer-peek-results.txt). The updated preview runs on 4512 with real form-provider credentials unset. The original comparison on 4511 is preserved.
