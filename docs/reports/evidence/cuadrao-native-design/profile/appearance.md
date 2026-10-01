# Profile details and appearance picker

September 30, 2026. Founder-authorized native UI iteration, not visual acceptance.
Replaces the icon-free proposal. Profile icons are restored; the appearance
control uses original miniature artwork and standard native state handling.

## Research

- [Claude dark-mode flow](https://mobbin.com/flows/38475637-0983-478b-ba47-530f2abb1313), 9 frames available: selection and downstream dark surfaces inspected through connector previews and the website. Borrow thumbnail choices, border state and direct application; do not claim every frame/motion timing was observed.
- [Claude selected Dark](https://mobbin.com/screens/664bd952-7201-4889-988e-7b6302ec7637): icon strokes, separator insets, compact groups, dark surfaces.
- [Things appearance](https://mobbin.com/screens/d3442fcb-c145-4b5b-83f1-d7a339731e44): short explanation of automatic/system behavior. Extra Black/widget variants are unnecessary for our current scope.
- [Notion theme](https://mobbin.com/screens/ac33be32-036a-4a22-bfd0-9c09d306c617): clear one-of-three selection. Its text-only presentation was not chosen because the founder prefers visual previews.
- [ChatGPT accent flow](https://mobbin.com/flows/0866b725-f273-4391-a205-c1bd25298143): in-place feedback and current values. Independent accent customization is not added.
- [Family settings](https://mobbin.com/screens/735de161-edcf-4044-8de1-6a28708610aa): inspected directly using the website Settings & Preferences filter after connector search incorrectly returned Setel/GoHenry. Those unrelated results were not used. Family demonstrates consistent icons and aligned current values.
- [Apple preferredColorScheme](https://developer.apple.com/documentation/swiftui/view/preferredcolorscheme(_:)): root appearance selection with nil for System.

Website metadata observed: Claude rating 4.83 (16), Productivity/AI, 56 flows and
158 UI elements in the inspected capture. Family was reached through Top rated;
its page showed 4.86 (51), Finance/Utilities and 251 screens, with two matching the
Settings & Preferences filter. These are dated Mobbin observations, not App Store
ratings or a claim of an objectively best app. Website discovery also exposes
Latest, Most popular, Top rated and Animations. Connector metadata includes app,
platform, IDs, canonical links, flow action labels and screen count/order; ratings
and website filters require the browser.

## Implementation

One local key, cuadrao.design.appearance, is the source for picker and preview root.
It reuses AppearancePreference's existing Light/Dark/System semantics but does not
write the connected app's appearance key. Adaptive palette values are shared across
active Cuadrao canvas surfaces rather than copying light/dark rules into each row.
The standard Apple sign-in preview button selects its native light/dark variant.
There are no new financial contracts, service calls, auth requests or model calls.

## Verification

- Final simulator and iPhone builds passed. Initial missing icon declaration was
  fixed before verification. git diff --check passed.
- Light > Dark changed the selected border/check and page colors in place.
- Home and Profile remained in Dark after navigation; app rebuild/relaunch retained
  Dark. Captured Home and Profile to inspect text/icon contrast.
- System returned to the simulator's Light setting; switching that same simulator
  to Dark changed the app in place. Restored the simulator to its original Light.
- Returned the design preview to Light for handoff. No new simulator/cache created.
- Installed the updated separate Cuadrao Preview on the paired iPhone.
- Captures are attached beside this note. Initial appearance captures remain visually
  applicable after the final Apple-button-only adjustment.

Dark palette remains a proposal. Full English, large-text, VoiceOver, all-screen
dark acceptance and physical touch checks are pending. Previous editing-input
bridge limitation still applies; no new claim of verified profile text entry.
