# Selection alignment — October 1, 2026

Verified source: `808c6413cc6b40e20b6f668fadcefb3e04423ac0`.
This evidence commit changes no application code.

The removed `CuadraoChoiceOption` mixed an icon-bearing selected Label with
unselected Text. Its callers were forecast space, plan-editor space, Home chart
currency and the reference gallery. `CuadraoChoiceMenu` now uses a native Picker
with text-only options and a system-owned selection gutter. Plan/group currency
creation also derives from this component. Appearance selection puts its check on
the preview instead of changing the centered caption's width. The searchable
currency list and chat preview-state rows already use trailing checks after a Spacer.

Two existing UI journeys passed on iPhone 18 Pro simulator
`8AFB6084-8918-416E-9164-E21061306BEC`, iOS 27:
- `CuadraoPolishUITests/testPlanScopeDoesNotChangeCreationDefault`
- `CuadraoPolishUITests/testLargeEnglishPlanControls`

Builds passed for simulator and signed physical iPhone target (build 3405).
The screenshots below were captured from the tested source before committing it;
source content is identical. They verify aligned labels and retain actual native
selection controls. The appearance caption fix was source-reviewed and compiled;
it was not a separate physical-device visual acceptance test.

- [Forecast, Spanish](forecast-choice-aligned-es.png)
- [Plan editor, Spanish](plan-space-choice-aligned-es.png)
- [Forecast, English dark and larger text](forecast-choice-dark-large-en.png)
