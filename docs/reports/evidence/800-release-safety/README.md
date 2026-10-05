# Native provider release safety

Issue #800. Integration base `875de09ac2115acec42e09060b92878aa5f18eff`.

The baseline exposed Google when Apple was off and loaded ignored local configuration in Release. `baseline-config.log` records the synthetic reproduction. `fixed-config.log` records 11 Debug and 11 Release configuration cases, with no skips or failures. The runner compiles the production configuration declaration and loads temporary synthetic plist bundles. It sends no provider requests.

The existing native configuration owner now requires Apple before exposing Google. Release uses a dedicated configuration that forces both flags off after local includes. The release runtime also returns the disabled configuration, including when build arguments override flags.

The connected UI test asserts provider accessibility identifiers against explicit test-runner expectations. Preview and welcome remain email-only. No identity token capture, deletion, name persistence, backend or hosted configuration changes are included.

Sequence Work into Verifiable Units kept release safety in one bounded PR. Simulator UI, compiled app plist checks, independent review and exact-head CI are required before landing. Apple authorization, revocation and phone acceptance remain #800 activation gates.
