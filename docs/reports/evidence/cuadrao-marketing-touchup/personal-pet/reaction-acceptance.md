# Accepted invalid-email reaction

The founder accepted the reaction and authorized updating PR #939 and obtaining green CI. Deployment and public forms remain held. This acceptance supersedes the local-only and pending-feedback notes for this reaction.

Runtime source is `0455fa4c2a7795064ea85b75879c83b09eec52e6`. Evidence source is `ffc028049`; this acceptance commit changes documentation only. The [capture manifest](screens/manifest.json), [clip](screens/personal-signup-demo.webm) and [browser results](invalid-email-browser-results.txt) remain valid because runtime bytes are unchanged.

Invalid submit produces one tilt and blink, retains the entered email and displays the localized error. Valid correction resets the pose. Native email validity and the existing rejected state remain the single owners. Reduced motion keeps a still expression, and network failures keep the pet calm. The local [demo](http://127.0.0.1:4513/personal) uses the same component and saves or sends no email.

## Verification

- Fresh build, lint, typecheck and the demo HTTP boundary test passed.
- Focused browser checks passed 49 tests, with one expected touch/pointer skip.
- Independent review of the runtime delta returned no findings. The parent corrected a test selector to exclude the unrelated Next.js route announcer. No runtime changes followed the review.
- Parent inspected desktop and mobile invalid-input captures. The live demo completed invalid input, correction, simulated success and Replay.
- On publish preparation, integration remains `43fac94de2672600079f312258908f05747a9d63` and is an ancestor of this branch. No new overlap or reconciliation is required. Merged-tree modularity has no violations.
- Original integration base is `bbf4da23f01296af4ac639386fe9a0960218a49f`. Existing reconciliation merge is `ece1aa067f6c810dd349fb57742a4eb0bd235ee9`.
- PR has no unresolved review threads and is conflict-free at preparation. Exact publication-head CI must be read from [PR #939 checks](https://github.com/lagarcess/argus/pull/939/checks). The terminal verification comment records the final head and run after CI completes.

## Continuation

Continue `codex/marketing-touchup-delivery` in the existing Marketing delivery worktree. Preview4512 and simulated signup4513 serve this accepted reaction. Comparison4511 and its archived source remain unchanged. Prior process IDs are observations; verify listener ownership before restarting.

Only Marketing files and evidence changed. No Business or Consumer product worktree, service, API, schema or provider configuration changed. PR remains draft and unmerged. No deployment, hosted change, public-form activation or real email is authorized.
