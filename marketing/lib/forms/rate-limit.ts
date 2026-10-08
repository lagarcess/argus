// Fixed-window counters held in memory. The service runs one instance, so a
// restart simply forgets recent attempts. This slows scripts down; it is not a
// security boundary, and the contract says so. A key is forgotten once its window
// has passed (swept at most once per window), so nothing outlives two windows.
export class WindowLimiter {
  private readonly hits = new Map<string, number[]>();
  private lastSweep = 0;

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly now: () => number = Date.now,
    private readonly maxKeys = 5000,
  ) {}

  // Returns the seconds to wait when the key is over its limit, otherwise null.
  check(key: string): number | null {
    const now = this.now();
    if (now - this.lastSweep >= this.windowMs) {
      this.lastSweep = now;
      this.prune(now);
    }
    const recent = (this.hits.get(key) ?? []).filter((at) => now - at < this.windowMs);
    if (recent.length >= this.limit) {
      this.hits.set(key, recent);
      return Math.max(1, Math.ceil((recent[0] + this.windowMs - now) / 1000));
    }
    recent.push(now);
    this.hits.set(key, recent);
    if (this.hits.size > this.maxKeys) this.prune(now);
    return null;
  }

  // How many keys are held right now.
  get tracked(): number {
    return this.hits.size;
  }

  private prune(now: number): void {
    for (const [key, times] of this.hits) {
      if (times.every((at) => now - at >= this.windowMs)) this.hits.delete(key);
    }
  }
}
