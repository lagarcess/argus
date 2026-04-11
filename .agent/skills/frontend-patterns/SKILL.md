---
name: Frontend Patterns
description: React and Next.js patterns for the Argus web application. Covers component structure, state management, and design system conventions.
---

# Frontend Patterns

## Tech Stack
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS (dark-mode first)
- **State**: React Query (TanStack Query) for server state, Zustand for client state
- **Auth**: NextAuth.js with Google/Facebook SSO
- **Charts**: Lightweight Charts (TradingView) for financial data visualization

## Project Structure (Future)
```
web/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── layout.tsx       # Root layout (dark theme, auth provider)
│   │   ├── page.tsx         # Landing / dashboard
│   │   ├── backtest/        # Strategy builder & results
│   │   └── api/             # API routes (proxy to Python backend)
│   ├── components/
│   │   ├── ui/              # Primitives (Button, Card, Input)
│   │   ├── charts/          # Equity curve, drawdown, candlestick
│   │   └── strategy/        # Strategy builder components
│   ├── lib/
│   │   ├── api.ts           # API client (fetch wrapper)
│   │   ├── auth.ts          # Auth configuration
│   │   └── utils.ts         # Shared utilities
│   └── hooks/               # Custom React hooks
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Component Conventions
- Use **functional components** exclusively (no class components).
- Co-locate component, types, and styles in the same directory.
- Prefix client components with `'use client'` only when needed.
- Server components by default (App Router).

```tsx
// components/strategy/StrategyCard.tsx
interface StrategyCardProps {
  name: string;
  sharpe: number;
  maxDrawdown: number;
}

export function StrategyCard({ name, sharpe, maxDrawdown }: StrategyCardProps) {
  return (
    <div className="rounded-xl bg-zinc-900 p-4 border border-zinc-800">
      <h3 className="text-lg font-semibold text-white">{name}</h3>
      <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-zinc-400">
        <span>Sharpe: {sharpe.toFixed(2)}</span>
        <span>Max DD: {(maxDrawdown * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}
```

## Design System
- **Dark mode first** — zinc-900 backgrounds, zinc-100 text.
- **Accent colors**: emerald for profit, rose for loss, blue for neutral actions.
- **Typography**: Inter font family via Google Fonts.
- **Spacing**: Use Tailwind's spacing scale consistently (p-4, gap-2, etc.).
- **Glassmorphism**: `backdrop-blur-md bg-white/5 border border-white/10` for cards.

## Data Fetching
```tsx
// Use React Query for all API calls
const { data, isLoading } = useQuery({
  queryKey: ['backtest', strategyId],
  queryFn: () => api.getBacktestResults(strategyId),
});
```

## API Integration
- Python backend exposes REST API (FastAPI).
- Next.js API routes proxy to Python backend in production.
- Use environment variables for API URLs: `NEXT_PUBLIC_API_URL`.

## Performance
- Use `React.memo()` for expensive chart components.
- Lazy load heavy components: `const Chart = dynamic(() => import('./Chart'))`.
- Debounce strategy parameter changes before triggering backtests.
