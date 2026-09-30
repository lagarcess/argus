# Home section customization

September 30, 2026. Native Cuadrao design canvas only.

Personalizar Inicio at the bottom of Home opens a native section-order editor.
Panorama, Próximamente, Cuentas and Movimientos are draggable rows. The logo,
space selector and bottom navigation remain outside the customizable content.
Done saves the order to this preview app's local AppStorage preference; Cancel
or swipe-dismiss discards the draft. Reset changes the draft to the starting
order. One preference applies across spaces. Empty content sections remain
absent, retaining their place when content becomes available. Account long press
and account-specific reordering retain their earlier meaning.

References inspected before implementation:
- [Revolut widget customization](https://mobbin.com/flows/82ab09c2-9855-44af-886f-82d3d00f6432)
- [Apple Fitness card reordering](https://mobbin.com/flows/e2b263dc-ca60-42eb-a2b3-911041b34731)

Verification on the existing iPhone 18 Pro simulator:
- Native build/run succeeded, build_run_sim_2026-09-30T23-37-50-949Z_pid12375_6dff1906.log.
- Dragged Cuentas from third to first using its native reorder handle.
- Saved, stopped and relaunched the app: Cuentas remained first on Home.
- Reopened editor, reset order, cancelled, reopened editor: saved Cuentas-first order retained.
- Screenshots reflect this same compiled source; only evidence/docs changed afterward.
- git diff --check passed.

English copy and VoiceOver move-up/move-down actions are included but were not
separately exercised in this pass. No backend, hosted data, financial rules,
new simulator or new derived-data directory. Home account fixtures remain
in-memory; only this local layout preference survives relaunch.

Open http://localhost:3200/ and scroll to Personalizar Inicio. Existing launch:
--cuadrao-design --cuadrao-home --home-populated. Use the same local.cuadrao.design
bundle, simulator 8AFB6084-8918-416E-9164-E21061306BEC and derived-data directory
/private/tmp/cuadrao-native-design-build.
