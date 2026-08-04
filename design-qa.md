# Guest settings and empty-state design QA

## Comparison target

- Source visual truth: `/var/folders/04/_3s7_2qd2z3_pxhb1jgjj5m00000gn/T/codex-clipboard-e5a4921f-3327-4f26-8871-7ebc0548ba13.png`
- Browser-rendered implementation: `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/desktop-light-en-menu-collapsed.png`
- Full-view comparison: `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/reference-vs-implementation.png`
- Focused menu comparison: `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/focused-reference-vs-menu.png`
- Route: `/chat`
- State: verified guest, empty temporary conversation, settings popover open

The source is a 670 × 410 px, 144 dpi reference crop. The desktop implementation
is a 1022 × 777 px, 72 dpi browser capture at a 1× CSS density. The combined
full-view comparison fits each input into a 900 × 760 px comparison cell. The
focused comparison preserves the 670 × 410 px source and fits a 432 × 280 px
implementation crop into the same 670 × 410 px comparison cell. The source is a
focused reference rather than a full Argus page, so the focused comparison is
the fidelity authority for the menu.

## Primary interactions tested

- Open and close the settings popover.
- Switch light, dark, and system theme controls.
- Open and close the shared centered language modal.
- Change English and Spanish without a guest profile write.
- Open feedback from the only remaining secondary menu row.
- Collapse and expand the sidebar.
- Send a message and transition from pre-message to post-message legal copy.
- Reload the temporary conversation.

No hydration errors, console errors, horizontal document overflow, or duplicate
temporary-chat notices were observed in the inspected states.

## Visual states inspected

- Desktop, light, English, sidebar collapsed, menu open:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/desktop-light-en-menu-collapsed.png`
- Desktop, light, English, sidebar expanded, menu open:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/desktop-light-en-menu-expanded.png`
- Desktop, dark, Spanish, sidebar collapsed, menu open:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/desktop-dark-es-menu-collapsed.png`
- Desktop, dark, Spanish, centered language modal:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/desktop-dark-es-language-modal.png`
- Mobile app surface, 354 × 844 CSS px inside the requested 390 px device
  frame, light, English, sidebar collapsed:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/mobile-390-light-en-collapsed.png`
- Mobile app surface, 354 × 844 CSS px, dark, Spanish, sidebar collapsed,
  corrected menu open:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/mobile-390-dark-es-menu-collapsed-v2.png`
- Mobile app surface, 354 × 844 CSS px, dark, Spanish, sidebar expanded:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/mobile-390-dark-es-expanded-v2.png`
- Mobile app surface, 354 × 844 CSS px, dark, Spanish, centered language
  modal:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/mobile-390-dark-es-language-modal-v2.png`
- Mobile app surface, 354 × 844 CSS px, dark, Spanish, post-message legal
  state after reload:
  `/Users/garces/.codex/visualizations/2026/07/24/019f9387-7fc6-7631-8750-072d4e7422e9/guest-settings-empty-state/mobile-390-dark-es-post-message-reload-v2.png`

## Required fidelity surfaces

- Fonts and typography: Argus typography and weights remain unchanged. Menu
  labels are deliberately smaller and quieter than the reference while staying
  legible, matching the approved request for a discreet treatment.
- Spacing and layout rhythm: the popover keeps the reference hierarchy with one
  segmented theme row above two clean action rows. The tighter radius, padding,
  and elevation fit the existing Argus chrome.
- Colors and visual tokens: active theme controls use a soft neutral fill in
  both themes. Borders, muted icons, focus rings, and shadows use existing
  black/white opacity tokens.
- Image and asset fidelity: no raster imagery is involved. All visible controls
  use the existing Lucide icon family; no handcrafted SVG, CSS art, or
  placeholder asset was introduced.
- Copy and content: English and Spanish labels, empty composer placeholders,
  legal text, and temporary-chat notice are localized. The product-approved
  Sign-in-only policy intentionally omits the source reference's Sign up action.
- Accessibility and interaction: the gear remains 44 × 44 CSS px, theme
  controls are labeled and pressed-state aware, the menu and modal close
  correctly, focus is restored to the gear, and the exact expiry timestamp
  remains available through the semantic time element.

## Findings

No actionable P0, P1, or P2 mismatch remains. The implementation preserves the
reference hierarchy while intentionally using Argus icons, a more compact
surface, and the locked Sign-in-only guest policy.

## Comparison history

1. The first mobile comparison found a P2 responsive issue: desktop right
   alignment placed the 244 px popover 35 px outside the 354 px app surface.
2. The popover was changed to center on its gear below the `sm` breakpoint while
   retaining desktop right alignment.
3. The revised dark Spanish mobile capture shows the full popover at x=33 px
   with both edges inside the viewport. `Idioma` and `Comentarios` are localized,
   and the temporary-chat notice remains beneath the composer.

## Follow-up polish

None required for this bounded pass.

final result: passed
