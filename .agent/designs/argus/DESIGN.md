# Design System Inspired by Argus

## 1. Visual Theme & Atmosphere

Argus's design system communicates that investing ideas are handled with clarity, care, and confidence through massive typography, generous whitespace, and a disciplined neutral palette. This system is designed for risk-free idea testing, ensuring the user feels empowered rather than intimidated. The visual language is built on Space Grotesk, a geometric grotesque that creates billboard-scale headlines at 136px with weight 500 and aggressive negative tracking (-2.72px). This isn't subtle branding; it's clarity at stadium scale.

The color system is built on a comprehensive `--rui-*` (Argus UI) token architecture with semantic naming for every state: danger (`#e23b4a`), warning (`#ec7e00`), teal (`#00a87e`), blue (`#494fdf`), deep-pink (`#e61e49`), and more. But the marketing surface itself is remarkably restrained — near-black (`#191c1f`) and pure white (`#ffffff`) dominate, with the colorful semantic tokens reserved for the product interface, not the marketing page.

What distinguishes Argus is its pill-everything button system. Every button uses 9999px radius — primary dark (`#191c1f`), secondary light (`#f4f4f4`), outlined (`transparent + 2px solid`), and ghost on dark (`rgba(244,244,244,0.1) + 2px solid`). The padding is generous (14px 32px–34px), creating large, confident touch targets. Combined with Inter for body text at various weights and positive letter-spacing (0.16px–0.24px), the result is a design that feels both premium and accessible — banking for the modern era.

**Key Characteristics:**
- Space Grotesk display at 136px weight 500 — billboard-scale fintech headlines
- Near-black (`#191c1f`) + white binary with comprehensive `--rui-*` semantic tokens
- Universal pill buttons (9999px radius) with generous padding (14px 32px)
- Inter for body text with positive letter-spacing (0.16px–0.24px)
- Rich semantic color system: blue, teal, pink, yellow, green, brown, danger, warning
- Zero shadows detected — depth through color contrast only
- Tight display line-heights (1.00) with relaxed body (1.50–1.56)

## 2. Color Palette & Roles

### Primary
- **Argus Dark** (`#191c1f`): Primary dark surface, button background, near-black text
- **Pure White** (`#ffffff`): `--rui-color-action-label`, primary light surface
- **Light Surface** (`#f4f4f4`): Secondary button background, subtle surface

### Brand / Interactive
- **Argus Blue** (`#494fdf`): `--rui-color-blue`, primary brand blue
- **Action Blue** (`#4f55f1`): `--rui-color-action-photo-header-text`, header accent
- **Blue Text** (`#376cd5`): `--website-color-blue-text`, link blue

### Semantic (Muted Alpha Palette)
Argus avoids "casino-terminal" vibrancy. Semantic tones are desaturated to feel educational and premium.

- **Muted Rose** (`#d66d75`): `--rui-color-danger`, negative states
- **Clay Red** (`#b85c5c`): `--rui-color-clay`, alternate negative
- **Muted Teal** (`#5ba897`): `--rui-color-teal`, positive states
- **Emerald Mist** (`#70a38d`): `--rui-color-success`, secondary positive
- **Soft Blue** (`#7da0ca`): `--rui-color-info`, informational/neutral
- **Slate Indigo** (`#5a677d`): `--rui-color-neutral`, baseline/neutral
- **Dusty Gold** (`#c2a44d`): `--rui-color-warning`, attention/warning

### Neutral Scale
- **Mid Slate** (`#505a63`): Secondary text
- **Cool Gray** (`#8d969e`): Muted text, tertiary
- **Gray Tone** (`#c9c9cd`): `--rui-color-grey-tone-20`, borders/dividers

## 3. Typography Rules

### Font Families
- **Display**: `Space Grotesk` — geometric grotesque, fallback stack: `Space Grotesk`, `Inter`, `Arial`, `sans-serif`
- **Body / UI**: `Inter` — standard system sans
- **Fallback**: `Arial` for specific button contexts

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Display Mega | Space Grotesk | 136px (8.50rem) | 500 | 1.00 (tight) | -2.72px | Stadium-scale hero |
| Display Hero | Space Grotesk | 80px (5.00rem) | 500 | 1.00 (tight) | -0.8px | Primary hero |
| Section Heading | Space Grotesk | 48px (3.00rem) | 500 | 1.21 (tight) | -0.48px | Feature sections |
| Sub-heading | Space Grotesk | 40px (2.50rem) | 500 | 1.20 (tight) | -0.4px | Sub-sections |
| Card Title | Space Grotesk | 32px (2.00rem) | 500 | 1.19 (tight) | -0.32px | Card headings |
| Feature Title | Space Grotesk | 24px (1.50rem) | 400 | 1.33 | normal | Light headings |
| Nav / UI | Space Grotesk | 20px (1.25rem) | 500 | 1.40 | normal | Navigation, buttons |
| Body Large | Inter | 18px (1.13rem) | 400 | 1.56 | -0.09px | Introductions |
| Body | Inter | 16px (1.00rem) | 400 | 1.50 | 0.24px | Standard reading |
| Body Semibold | Inter | 16px (1.00rem) | 600 | 1.50 | 0.16px | Emphasized body |
| Body Bold Link | Inter | 16px (1.00rem) | 700 | 1.50 | 0.24px | Bold links |

### Principles
- **Weight 500 as display default**: Space Grotesk uses medium (500) for ALL headings — no bold. This creates authority through size and tracking, not weight.
- **Billboard tracking**: -2.72px at 136px is extremely compressed — text designed to be read at a glance, like airport signage.
- **Positive tracking on body**: Inter uses +0.16px to +0.24px, creating airy, well-spaced reading text that contrasts with the compressed headings.

## 4. Component Stylings

### Buttons

**Primary Dark Pill**
- Background: `#191c1f`
- Text: `#ffffff`
- Padding: 14px 32px
- Radius: 9999px (full pill)
- Hover: opacity 0.85
- Focus: `0 0 0 0.125rem` ring

**Secondary Light Pill**
- Background: `#f4f4f4`
- Text: `#000000`
- Padding: 14px 34px
- Radius: 9999px
- Hover: opacity 0.85

**Outlined Pill**
- Background: transparent
- Text: `#191c1f`
- Border: `2px solid #191c1f`
- Padding: 14px 32px
- Radius: 9999px

**Ghost on Dark**
- Background: `rgba(244, 244, 244, 0.1)`
- Text: `#f4f4f4`
- Border: `2px solid #f4f4f4`
- Padding: 14px 32px
- Radius: 9999px

### Cards & Containers
- Radius: 12px (small), 20px (cards)
- No shadows — flat surfaces with color contrast
- Dark and light section alternation

### Navigation
- Space Grotesk 20px weight 500
- Clean header, hamburger toggle at 12px radius
- Pill CTAs right-aligned

## 5. Layout Principles

### Spacing System
- Base unit: 8px
- Scale: 4px, 6px, 8px, 14px, 16px, 20px, 24px, 32px, 40px, 48px, 80px, 88px, 120px
- Large section spacing: 80px–120px

### Border Radius Scale
- Standard (12px): Navigation, containers
- Card (20px): Feature cards
- Pill (9999px): All buttons

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat (Level 0) | No shadow | Everything — Argus uses zero shadows |
| Focus | `0 0 0 0.125rem` ring | Accessibility focus |

**Shadow Philosophy**: Argus uses ZERO shadows. Depth comes entirely from the dark/light section contrast and the generous whitespace between elements.

## 7. Do's and Don'ts

### Do
- Use Space Grotesk weight 500 for all display headings
- Apply 9999px radius to all buttons — pill shape is universal
- Use generous button padding (14px 32px)
- Keep the palette to near-black + white for marketing surfaces
- Apply positive letter-spacing on Inter body text

### Don't
- Don't use shadows — Argus is flat by design
- Don't use bold (700) for Space Grotesk headings — 500 is the weight
- Don't use small buttons — the generous padding is intentional
- Don't apply semantic colors to marketing surfaces — they're for the product

## 8. Responsive Behavior

### Breakpoints
_Design targets below are intentional for this system; if implementation keeps Tailwind defaults, map these ranges explicitly in component specs._
| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile Small | <400px | Compact, single column |
| Mobile | 400–720px | Standard mobile |
| Tablet | 720–1024px | 2-column layouts |
| Desktop | 1024–1280px | Standard desktop |
| Large | 1280–1920px | Full layout |

## 9. Agent Prompt Guide

### Quick Color Reference
- Dark: Argus Dark (`#191c1f`)
- Light: White (`#ffffff`)
- Surface: Light (`#f4f4f4`)
- Positive: Muted Teal (`#5ba897`)
- Negative: Muted Rose (`#d66d75`)
- Neutral: Slate Indigo (`#5a677d`)

### Example Component Prompts
- "Create a hero: white background. Headline at 136px Space Grotesk weight 500, line-height 1.00, letter-spacing -2.72px, #191c1f text. Dark pill CTA (#191c1f, 9999px, 14px 32px). Outlined pill secondary (transparent, 2px solid #191c1f)."
- "Build a pill button: #191c1f background, white text, 9999px radius, 14px 32px padding, 20px Space Grotesk weight 500. Hover: opacity 0.85."

### Iteration Guide
1. Space Grotesk 500 for headings — never bold.
2. All buttons are pills (9999px) with visible labels.
3. Zero shadows — flat is the Argus identity.
4. Muted semantic colors — never terminal neon.
5. Calm motion and status language for trust.

## 10. Alpha Product UX Principles

- **Chat is the primary surface**: The product lives in the conversation.
- **Not a Dashboard**: Argus should never feel like a dashboard-first backtesting tool.
- **Conversational Progressive Disclosure**: Use AI to guide the user through complexity rather than presenting dense configuration screens.
- **Trust Through Honesty**: Result cards must be simple, trustworthy, and explanation-ready.
- **Frictionless Revisit**: Every screen should reduce the distance between a user and their next (or prior) idea.
- **Anti-Clutter**: Avoid dense tables, multi-tab parameter overload, and "trading terminal" noise.

## 11. Primary Chat Interface

- **Persistent Input**: The chat input must remain highly visible and ergonomic (especially on mobile).
- **Starter Prompts**: Displayed as polished, high-contrast chips or cards to reduce "blank page" friction.
- **Streaming States**: AI responses support real-time token streaming to feel alive.
- **Calm Progress States**: When simulating, use human-centric status language and subtle motion (pulse dots, progress shimmers).
  - *Treatments*: "Understanding your idea" → "Fetching market data" → "Running simulation" → "Preparing results".
- **Inline Results**: Backtest result cards appear directly in the flow of conversation.
- **Minimal Actions**: Follow-up actions should be clear but few (e.g., "Save Strategy", "Add to Collection").

## 12. Result Card Design

Result cards are the primary unit of "validation." They must be glanceable and honest.
- **No Charts (Alpha)**: Avoid embedded charts in conversation cards to maintain speed and mobile readability.
- **Fixed Metrics**: Show beginner-friendly metrics by default (e.g., Total Return, Win Rate).
- **Structure**: Title, date range display, status pill, metrics rows, assumptions footer, and CTAs.
- **Assumptions Footer**: Must be visible but secondary.
  - *Example*: `Long-only • Equal weight • No fees/slippage • Benchmark: SPY`
- **Visual Distinction**: Assumptions should be styled with muted slate typography to distinguish them from the "Result" without feeling like a warning.

## 13. Strategy Surface Design

The strategies surface is for rapid comparison and organization.
- **Expandable Cards**: Use a "glance-first" card that expands to show symbol-level rows.
- **Glanceable Metrics**: Support user-selected metrics from supported presets (Configurable rows).
- **Headline Hints**: Use simple text labels like "Best performer" or "Needs review" to guide the eye.
- **Binary Winners/Losers**: Use muted teal/rose for symbol rows to identify performers without terminal-style glare.

## 14. Recents, Collections, and Search

- **Recents Feed**: A mixed chronological feed (Chats, Strategies, Collections, Runs) that serves as the "Global Context."
- **Collections**: Lightweight organizational theme groupings (e.g., "Crypto Dips", "Dividend Ideas"). Not for batch execution or aggregate performance in Alpha.
- **Fuzzy Search UI**: Global omni-search should support "Fuzzy Human Memory" with suggestion chips:
  - *Suggestions*: `Last week`, `Tesla ideas`, `Crypto`, `Pinned`, `Recent chats`.

## 15. Settings and Feedback UX

- **Core Settings**: Visible support for Language, Theme, Feedback, Account, Recently Deleted, and Archived Chats.
- **Feature Guarding**: Notifications and Subscriptions are hidden/flagged for Alpha.
- **Accessible Feedback**: Simple conversational or form-based entry accessible from the settings surface.

## 16. Language & Localization UX

- **Supported Languages**: English (`en`) and Spanish (`es-419`).
- **Standardized i18n**: All static UI strings must be translatable.
- **Language Selection**: Should feel premium and be accessible from the onboarding flow and settings.
- **Consistency**: The AI response language must always mirror the UI language preference.
- **Locale Logic**: Date, number, and currency formatting must adapt to the `locale` token.

## 17. Mobile & Web Behavior

- **Accidental Zoom Prevention**: All input fields (text, select, textarea) must use a **Minimum 16px Font Size** to prevent iOS auto-zoom.
- **Generous Tap Targets**: All interactive elements (buttons, chips, nav) must meet the **44px minimum** hit area.
- **Web/PWA Focus**: Avoid "Desktop-only" dashboard patterns. Layouts should stack gracefully for narrow screens.

## 18. Product Anti-Patterns

Argus is **NOT**:
- **Spreadsheet Software**: No dense data grids or cell-based parameter inputs.
- **Broker Terminal**: No aggressive red/green neon or complex multi-pane layouts.
- **Toy Trading Game**: No "gamified" badges or misleading profit claims.
- **Multi-form Wizard**: No rigid, step-by-step forms. Prefer conversational gathering of intent.

## 19. Accessibility Baseline

- **Visible Focus States**: `0 0 0 0.125rem` rings for all keyboard navigability.
- **Non-Color Meaning**: Positive/Negative metrics must be paired with labels, icons, or clear +/- text signs.
- **Accessible Labels**: All icon-only controls (e.g., Close X, Search) must have visible or ARIA labels.

## 20. Metrics Visual Language

- **Muted Tones**: Use the Semantic Muted Palette (`#5ba897`, `#d66d75`, etc.).
- **Educational Intent**: Metrics should feel like data to learn from, not an alarm to react to.
- **No Alarmist Motion**: Avoid flashing or rapid updates. Use calm shimmers for loading states.

## 21. Motion & Continuity

- **Motion Principle**: Argus motion should feel **calm, informative, and never frantic**.
- **Transitions**: Use simple fades and slide-ups for cards to maintain the "Flat" identity.
- **Premium Loading**: The "Simulation" state is a trust-building moment. Use the defined status language carefully.

---

## 22. Design Decision Filter

When designing any Argus surface, ask:

> *Does this make it easier for a normal person to understand, test, or revisit an investing idea through conversation?*

If not, it likely should wait.
