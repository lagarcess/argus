## 2025-04-06 - [React Memoization for Large SVGs]
**Learning:** Large inline SVG components in Next.js (like the Equity Curve chart mock) can cause significant UI thread lag during parent component re-renders.
**Action:** Always extract complex static or pure UI visualizations into separate components wrapped in `React.memo` to eliminate unnecessary diffing overhead.
