# Personal signup pet and phone

Source `c8eab10647c56a49591033f5e5a026bb8a5befa6`, October 9, 2026. Founder requested keeping the left-hand copy and signup, replacing the Home preview with a hand-held phone showing the native welcome screen, and adding a square pet that watches the cursor and delivers an envelope after signup succeeds. The founder chose the welcome screen with the logo and signup button. This is a local design iteration pending visual acceptance.

## Behavior

The original code-native hand holds the unchanged native preview on the right. The pet peeks from the email field, follows fine pointers with its eyes, and becomes excited during submission. A successful registered response starts one 1.1-second flight. The envelope leaves the CTA and the pet hops with it toward the central phone logo. A ripple marks arrival and the pet settles there. Confirmation appears and receives focus immediately. Errors and unexpected responses preserve the email and produce no flight. Signup request, persistence, privacy and duplicate behavior remain unchanged.

The Model the Domain principle kept SignupState as the only owner of request truth. Decorative state contains measured positions only. The parent and independent design judge selected the smaller CSS animation sketch after comparing two designs. See [decision](design-decision.md), [candidate A](design-a.md), and [candidate B](design-b.md).

Mobile stacks the phone below the intake. A flight is skipped if its destination is offscreen. No decorative auto-scroll occurs. Fine-pointer eyes reset on pointer exit and keyboard navigation. Reduced motion skips eye movement, bounce and flight. Scrolling, resizing or changing motion preference settles an active flight. A visual review caught a 39-pixel headline shift during confirmation; explicit grid rows remove that shift and a browser assertion guards it.

## Asset provenance

The welcome image is copied unchanged from `docs/reports/evidence/cuadrao-release-ui/2026-10-03-w1/release-design-launch-light.png`. Source dimensions are 1320×2868. The [native evidence](../../cuadrao-release-ui/README.md) records the October 3 simulator design capture. It is historical design evidence, not a claim about the current shipping app. The website caption says it is a welcome preview whose design may change. The English caption identifies the Spanish preview.

Served asset `marketing/public/cuadrao-site/personal-welcome-preview.png` has SHA-256 `8dc8c6e298742c0bfcec5261a1d4f79d93d4d2733ca46b1a2bc6356b23b22f7c`. The hand, pet and envelope are original SVG/CSS graphics. No Base artwork was extracted. The native logo was not redrawn. Consumer files, app services and simulators were not modified or launched.

## Verification

- Fresh production build, Marketing typecheck, lint and diff checks pass.
- 33 Personal signup/motion browser checks pass. One pointer-only test is intentionally skipped in the touch project. Tests cover delayed response gating, success and natural settlement, duplicate signup, unavailable storage, unexpected responses and retry, focus, pointer tracking, scroll cancellation, reduced motion, 320/390-pixel layouts, privacy and pre-hydration behavior in both languages.
- Four focused automated WCAG 2.1 AA checks pass for Personal in ES/EN on desktop and mobile.
- The parent inspected final desktop/mobile screenshots and in-flight/settled captures. Independent scoped implementation review and the final layout-delta review are clean, with zero actionable findings, comments to remove or suppressions.
- [Browser results](browser-results.txt), [accessibility results](accessibility-results.txt), [build results](build-results.txt), and [exact-source capture manifest](screens/manifest.json).
- [Desktop idle](screens/personal-es-1440-idle.png), [desktop flight](screens/personal-es-1440-flight.png), [desktop settled](screens/personal-es-1440-success.png), [mobile](screens/personal-es-390-idle.png), and [short demo recording](screens/personal-signup-demo.webm). Matching English screenshots are in the same directory.

The recording and screenshots intercept the browser's signup request with a registered fixture. No request reaches the signup server or a provider. These demonstrate animation, not a real registration. The existing signup suite separately exercises storage with its mock provider. No physical iPhone/Safari acceptance is claimed.

## Continue safely

Resume `codex/marketing-touchup-delivery` in the existing Marketing worktree with PR #939. Updated preview is `http://127.0.0.1:4512/personal`, with real provider credentials unset. Comparison 4511 remains preserved. The subsequent documentation/evidence commit changes no Marketing runtime source. No push, merge, hosted change, publication, public-form activation or real email occurred. All workers have handed back ownership.

From `marketing/`, after building, use isolated test ports:

```sh
CI=1 MARKETING_E2E_SITE_PORT=4540 MARKETING_E2E_PUBLIC_PORT=4541 MARKETING_E2E_MOCK_PORT=4542 bun run test:e2e e2e/personal.spec.ts e2e/personal-motion.spec.ts
CI=1 MARKETING_E2E_SITE_PORT=4540 MARKETING_E2E_PUBLIC_PORT=4541 MARKETING_E2E_MOCK_PORT=4542 bun run test:e2e e2e/site.spec.ts --grep 'personal.*automated WCAG'
bun run scripts/capture-personal-pet.mjs
```

Keep current forms disabled from real providers until the founder approves activation. The saved demo is the safe way to review successful delivery in the meantime.
