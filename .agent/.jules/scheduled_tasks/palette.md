# Palette 🎨 — UX Guardian Reference

**Mission:** Find and implement micro-UX improvements (loading states, accessibility, design system alignment).

**Scope:** Next.js 15 frontend (`/web/`), focus on trader workflows (builder, results, history, mobile)

**Improve:**

- Functional UX: Loading states, validation feedback, empty states, disabled explanations
- Accessibility: ARIA labels, color contrast, keyboard navigation
- Trading clarity: "Profitable?" badge, equity curve tooltips, status indicators
- Mobile PWA: Responsive cards, touch targets (48px+), install prompt

---

## Key Commands

**Frontend Development:**

```bash
cd web
bun install
bun run dev      # Manual testing on desktop & mobile

# Validation
bun run lint
bun run format
bun run build

# Mobile Testing
# Chrome DevTools: Device Mode (iPhone 12 Pro)
# Test in PWA mode (press 'i' in dev tools)
```

---

## Good Patterns ✅

### Loading State

```typescript
const ResultsPage = () => {
  const { data: backtest, isLoading } = useQuery(getBacktest);

  return (
    <div>
      {isLoading && (
        <div className="animate-pulse space-y-4">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-12 w-3/4" />
        </div>
      )}
      {backtest && <EquityCurve data={backtest.equity_curve} />}
    </div>
  );
};
```

### Form Validation

```typescript
const StrategyBuilder = () => {
  const {register, formState: {errors}} = useForm({
    resolver: zodResolver(BacktestRequestSchema),
  });

  return (
    <form>
      <select {...register("asset")}>
        <option>Select asset...</option>
        <option value="BTC/USDT">Bitcoin (BTC/USDT)</option>
      </select>
      {errors.asset && (
        <span className="text-red-500">{errors.asset.message}</span>
      )}

      <button disabled={isSubmitting || Object.keys(errors).length > 0}>
        {isSubmitting ? "Running..." : "Run Backtest"}
      </button>
    </form>
  );
};
```

### Mobile-First Cards

```typescript
const BacktestCard = ({ backtest }: { backtest: Backtest }) => (
  <div className="p-4 border rounded-lg hover:shadow-md transition space-y-3">
    {/* 48px+ touch targets */}
    <button
      onClick={() => navigate(backtest.id)}
      className="w-full py-2 px-3 text-left"
      aria-label={`View ${backtest.asset} results`}
    >
      <div className="font-semibold">{backtest.asset}</div>
      <Sparkline data={backtest.sparkline} height={30} />

      <Badge variant={backtest.metrics.total_return > 0 ? 'success' : 'error'}>
        {backtest.metrics.total_return > 0 ? '✓ Profitable' : '✗ Loss'}
      </Badge>
    </button>
  </div>
);
```

---

## Anti-Patterns ❌

❌ No loading skeleton (user sees blank screen)
❌ Form submits with validation errors
❌ Buttons <44px without spacing (mobile frustration)
❌ Charts missing tooltips (readability)
❌ No "empty state" message when no backtests exist
❌ Color contrast <4.5:1 (WCAG fails)
❌ Form fields lack ARIA labels

---

## Design System

Use **Robinhood design tokens:**

- Primary (brand): `#00A86B` (green)
- Success (profit): `#27AE60`
- Loss (negative): `#E63946` (red)
- Neutral: `#6C757D` (gray)
- Font: `Inter, -apple-system, BlinkMacSystemFont`

---Tolerance
## 🌳 Branching & PRs

Follow the naming convention in `.agent/.jules/README.md`:
- `feat/ux-...` or `web/feat/palette-...`
- For vague UX tasks, infer a branch name that reflects the component or flow improved.
- All improvements MUST be committed to a short-lived feature branch before opening a PR.

### PR Labels
Suggest labels: `feature` (or `refactor`), `web`, and `low-priority`.

---

## Journal

**Only log meaningful UX improvements** (verified with user feedback, accessibility fix, design system alignment).

Write to: `.agent/.jules/journal/palette.md`

**FEEDBACK LOOP (Critical): Before writing, check journal for:**

- Did I propose this exact UX improvement before?
- Was it already implemented? (Mark as RESOLVED + PR number)
- Has the UI component already been fixed? (Write "no finding" and stop)

**Example journal entries:**

✓ **Resolved improvement:**

```markdown
## [2026-04-07] - Follow-up: Mobile Touch Targets Fixed

- **Previous:** proposed 2026-04-05 (buttons too small on mobile)
- **Current status:** IMPLEMENTED + merged in PR #47 (8px → 12px padding)
- **Result:** RESOLVED #47
```

✓ **New UX proposal:**

```markdown
## [2026-04-07] - Proposal: Accessibility: Backtest Results Contrast

- **Issue:** Results table text fails WCAG contrast ratio (4.5:1)
- **Proposal:** Update colors to meet AA standard (7:1)
- **Status:** PENDING HUMAN REVIEW + PR
```

✓ **No action:**

```markdown
## [2026-04-07] - Design System Audit: All Current

- **Status:** Touch targets ≥44px, colors WCAG AA, RH design system aligned
- **Result:** NO CRITICAL FINDINGS
```

If no clear UX gap exists (design already matches system, accessibility OK), **stop—no action needed**.
