# Cuadrao Plan — Mobbin research and proposed direction

Research date: October 1, 2026. Design proposal, not an implementation or product-scope lock.

## Brief

Make financial planning approachable, personal and enjoyable. Plan helps someone see where their current pace leads and explore changes before committing. Preserve Cuadrao's Spanish-first voice, English parity, chosen icons, existing navigation, quiet space selector, and reusable financial records. Home can summarize the same forecast; it must not calculate a second one.

## Evidence and limits

Inspected 43 returned image previews across focused screen searches and six sampled flows. Flow metadata provides app, action labels, sequence positions and total screen count. Longer flows return sampled frames: the 21-screen Monzo flow and 16-screen Gentler Streak flow were not inspected frame by frame. Screens show design states; they do not establish animation timing, haptics or production calculations. Capture dates and app versions were not supplied by these search results. References are specific captured patterns, not claims about each app's latest release.

Quality signals checked separately from Mobbin: US App Store listings showed [Gentler Streak 4.7](https://apps.apple.com/us/app/gentler-streak-workout-tracker/id1576857102), [Airbnb 4.8](https://apps.apple.com/us/app/airbnb/id401626263?see-all=reviews), [Finch 4.9](https://apps.apple.com/us/app/finch-self-care-pet/id1528595748), and [Copilot Money 4.8](https://apps.apple.com/us/app/copilot-track-budget-money/id1447330651?platform=ipad). These are selection signals, not a ranking or proof that every interaction is good. Apple also documents Gentler Streak's [2024 Design Award and humane approach](https://developer.apple.com/news/?id=3m0ht22s).

## Observations and proposed adaptations

| Reference | Observed detail | Proposed Cuadrao adaptation |
| --- | --- | --- |
| [Gentler Streak current state](https://mobbin.com/screens/c991401a-cc03-4eb2-9143-e775e8b15865) | A human explanation precedes a visual status range and a small set of recommendations. | One useful sentence about the month above the chart. Show a next step appropriate to the situation. Avoid shame, moral scores and artificial streaks. |
| [Gentler Streak workout entry](https://mobbin.com/flows/30abfa6c-40b1-4333-80b0-85a4b26017f2) | An effort slider is labeled with an understandable description and a usual range; optional fields remain secondary. | A scenario control couples amount, cadence and consequence. Exact numeric entry accompanies the slider. The original setting remains visible. This reference is workout logging, not verified forecasting behavior. |
| [Airbnb wishlists](https://mobbin.com/screens/47795b4e-7aae-42ca-874f-9ae564feb94c) | Personal names and photo collections make saved intentions recognizable. | Optional cover photo or illustration for Samaná, a laptop or a home project, with one useful progress sentence. Keep images out of utilitarian monthly summaries when they add no meaning. |
| [Airbnb save flow](https://mobbin.com/flows/afa1cff0-f3aa-4a48-8462-0001cde57e15) | A small naming sheet preserves the underlying context; confirmation offers Change. | Let people begin a plan with a name, then add the details that its purpose needs. Save feedback is quiet and offers a way back. Avoid a mandatory questionnaire. |
| [Monzo naming](https://mobbin.com/screens/75e96ac3-31aa-497d-9158-ecfe2d41182f) and [cover choices](https://mobbin.com/screens/133a0b11-0191-48a3-8db0-ec195dfce700) | Editable cover, suggested names and camera-roll/gallery options. | A few helpful starting points plus a free name. Personalization remains optional and editable later. A Cuadrao plan is not a new bank account. |
| [Monzo savings flow](https://mobbin.com/flows/c4c521ce-8566-4c6f-a5b6-01c6c1443bbc) | Goal amount is optional; target date and banking options appear later. Creation has a celebration. | Support an unfinished intention honestly. Ask for amount/date when needed to calculate. Reserve meaningful celebration for actual progress, rather than every setup action. Do not import banking setup or money-moving assumptions. |
| [Stake calculator](https://mobbin.com/screens/88680915-5c5d-4d37-9738-a97d4b8453c3) | Large area chart, editable amount chips, recurring amount slider and cadence controls on the same surface. | Keep a compact chart visible above scenario controls. Adjusting an amount previews the result in place. Borrow the interaction structure, not investment assumptions or returns. |
| [Monzo projection](https://mobbin.com/screens/a196ebe3-0c04-4b4e-8241-201b961696a7) | Contribution slider sits beneath a projection with separately labeled values and a likely range. | Differentiate facts and estimates with labels and line treatment. Only draw a numeric uncertainty band if the forecast model actually supports one. |
| [Copilot spending pace](https://mobbin.com/screens/4ed48c3b-8d88-4dab-b69f-89f0c67953fc) | Current spending line and reference line share a clear chart, with a selected endpoint label. | Direct chart labels, a clear Today boundary, and a compact value readout. Avoid multiple charts competing for first glance. |
| [bunq balance prediction](https://mobbin.com/screens/f5ca0ce0-971b-4d41-a5e3-d957be27fbec) | Solid history becomes a dotted projection; a selected date/value and short explanatory message accompany it. | Separate actual history from projected future, and make upcoming changes explainable. Forecasting already exists elsewhere; differentiation must come from the complete experience. |
| [Finch goal personalization](https://mobbin.com/flows/bae84409-cb5a-4b81-a48f-a5d039f22300) | A personal goal can change its emoji and retains its identity when returning to the goal card. | Let people choose an icon or cover without adding a game economy. Cuadrao's conversational personality is already the companion. |

Additional comparisons inspected: [Quicken projected cash flow](https://mobbin.com/screens/7bb55ca0-a5c5-4002-86f7-67a3f990d02d), [The Outsiders explanation and chart](https://mobbin.com/screens/63fbd860-c86d-4c1b-9112-4158b1f2d10e), [Oura trends](https://mobbin.com/screens/ee9deea1-7c4e-4efa-b7b1-2d08b4de97c3), [Noom goal endpoint](https://mobbin.com/screens/120e1d70-ca80-42a1-96df-1b3fd346ebec), [GetYourGuide wishlists](https://mobbin.com/screens/d6bfc662-dd16-4e15-beef-27eff597c727), and [Buddy first goal](https://mobbin.com/screens/2d0525a9-72f2-4b7f-bc85-bec9b4591af5). They provide contrasts in density, orientation and empty-state behavior; they are not all recommended visual models.

## Recommended first experience

1. **Plan at a glance.** Preserve the space row. A calm display heading, “Así va tu mes,” leads into a forecast with one clear projected closing amount. Label what that amount represents, its currency, period and included accounts. Supporting details are available in “Cómo lo calculamos.”
2. **Read the path.** Actual values use a solid line; estimates use a dashed line after Today. Tapping or moving across the chart reveals a date and value. Salary and bill markers explain material jumps. Keep the graph faithful: smoothing must not invent balances between known events.
3. **See personal intentions.** A small set of named plans follows the chart, with optional imagery and concise meaningful progress. Keep money reserved for a goal distinguishable from spendable money. Photo cards must remain legible in large text.
4. **Explore one change.** “¿Y si…?” opens controls while keeping the chart visible. Adjust one amount or date. A subdued original path and a clearly labeled alternative show the difference. “Probando” identifies the unsaved state; “Aplicar” saves and “Restablecer” returns to the original. Closing an unchanged preview needs no confirmation.
5. **Continue with Cuadrao.** A contextual conversation can reference the current plan and proposed change. Its eventual agentic write path uses the same plan owner and review rules. Research does not authorize provider integration or cross-app execution now.

## Details that make it feel finished

- Warm neutral canvas, Cuadrao green, restrained personal accent colors. Preserve the existing type pairing and selected icon shapes.
- A soft chart fill adds depth. Header/footer blur is limited to scrolling beneath persistent controls, not placed over values or everywhere on screen.
- Stable plot scale during a comparison; amounts align and keep their width while changing. No layout jumps while dragging.
- Motion explains changes: the alternative path transitions from the original; save returns to the same context and scroll position. No perpetual pulsing or bouncing.
- Light haptic feedback only for meaningful selections or saved changes; details here are proposals, not measured Mobbin behavior.
- Gesture actions also have visible controls. Exact amount entry, VoiceOver labels, large-text layouts, contrast and Reduce Motion remain first-class.
- Red communicates a real problem or destructive action, not a judgment about spending. An amber explanation can draw attention to an assumption or possible shortfall.
- Copy is short, warm and evidence-based: “Samaná va cogiendo forma” can accompany actual progress; “Moverlo a noviembre te dejaría más margen” requires a supported comparison. Avoid saying a purchase is safe merely because the month ends positive.

## Forecast truth that affects design

Show the projected low point as well as month-end when a bill causes a shortfall before the next income. Expected income is not confirmed cash. Transfers must not inflate income/spending; linked goal contributions must not be counted twice. Separate currencies until a deliberate conversion model exists. A single owner supplies Home and Plan.

For a cold start, let someone create a named plan or supply a starting balance and expected payments. Do not draw a confident pace forecast without enough history. When information is incomplete, explain what is missing and let the person explore with explicit assumptions. The surface should stay useful without fabricated certainty.

## What to prototype next

One coherent native design journey: Plan overview → personal plan → change amount/date → compare → apply or reset. Include an empty start, a normal month and a temporary shortfall. Spanish first with English parity, then visual checks on the designated simulator and physical iPhone. Keep existing financial, navigation and chat ownership; resolve forecast computation contracts separately before connecting real records. No implementation, deployment or new agent integration was performed as part of this research.

## Gesture and motion follow-up

The founder asked for a balance of gestures and minimal input, building on Chat's tactile interaction. Additional research inspected six sampled flows and two chart screens. Browser inspection opened Stake's Screens and Prototype modes, followed its calculator entry hotspot, and checked the available actions. Stake's More info reported an upload date of February 23, 2026. Sunlitt also exposed Screens and Prototype. These inspected pages did not expose original motion playback; prototype transitions must not be attributed to the native apps. Animation timing and haptics below remain Cuadrao proposals.

Additional references:

- [Stake calculator flow](https://mobbin.com/flows/b518dec0-280a-4c42-bcd0-726868733baf): presets, numeric inputs and sliders lead to a chart with an inline recurring-amount control. Preserve the chart while adjusting; do not copy the preliminary form-heavy setup wholesale.
- [Me+ time adjustment](https://mobbin.com/flows/6ee73fbd-9575-40af-ab95-ec56fc3aa12d): a large selected duration above a horizontal marked ruler. Adapt the visible ruler affordance to target-month exploration, with a date picker available on tap.
- [Sunlitt time exploration](https://mobbin.com/flows/c5f744b4-49ab-4c17-b48d-e5453d2cc5e6): date/time changes appear alongside different sun positions and shadows. The useful principle is a visible causal relationship between input and outcome. Exact drag behavior was not established from the sampled states.
- [Oura selected chart value](https://mobbin.com/screens/f29a87f3-8e4f-447d-87c7-852b43d9f2ad): a date/value callout is attached to the selected mark. Adapt this to reading a financial timeline, not editing recorded balances.
- [Apple gestures](https://developer.apple.com/design/human-interface-guidelines/gestures/): familiar, discoverable interactions and alternatives to custom shortcuts.
- [Apple discoverable design](https://developer.apple.com/videos/play/wwdc2021/10126/): make interactive possibilities apparent; hidden gestures should accelerate actions that remain otherwise available.

Proposed minimal gesture vocabulary:

| Intent | Direct interaction | Visible alternative / constraint |
| --- | --- | --- |
| Understand the month | Tap or slide across the chart to select a date and see its amount/events. | Date selection and accessible chart values. This never edits the forecast or records. |
| Try another monthly amount | Drag a visible slider thumb inside the scenario panel. | Tap the displayed amount for exact entry; accessible increment/decrement. |
| Try another target date | Move a labeled month ruler; selected month snaps into place. | Tap the date to use the native picker. Applies only to an adjustable goal date, not a contractual bill due date. |
| Keep the result | Tap Aplicar after exploring. | One clear durable save, with the exact proposed change visible. Release of a drag never saves. |

A familiar gesture only gains an extra job when its scope is clear. Chart touch reads values; a labeled scenario control changes an assumption. Do not overload the same chart drag with editing, navigation and comparison. Delay expensive explanatory text updates until the selected value settles; numeric preview feedback follows the finger immediately. Keep the chart scale stable within a comparison. Tiny feedback at meaningful increments can be tested on hardware, without vibrating at every pixel.

While dragging, keep navigation geometry steady and retain touch ownership. Do not bounce, hide, rearrange or reactivate the menu bar underneath the gesture. Vertical scrolling and iOS edge-back remain available outside the active control. A brief contextual hint such as “Desliza para probar” belongs next to the control, not in a tutorial covering the chart. Any snapping motion settles on release and respects Reduce Motion; it must not delay input.

The target example is: open Samaná → adjust one visible contribution control → see the projected date and effect on this month → Aplicar or Restablecer. Existing known amounts can prefill it; missing facts still require honest input. This is a proposed interaction direction, with no native code or device installation performed in this research follow-up.
