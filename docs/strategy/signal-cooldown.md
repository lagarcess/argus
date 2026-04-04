# Signal Cooldown Guide

This guide explains the **Hybrid Cooldown Logic** implemented in the Crypto Sentinel engine. This mechanism prevents "revenge trading" and reduces noise by enforcing a wait period after a successful trade exit.

---

## Overview

### Problem Statement
After a signal reaches its exit targets (TP1, TP2, or TP3), generating a new signal for the same symbol immediately can lead to:
- **Whipsaw Trades**: Reacting to minor momentum reversals.
- **Over-leverage**: Opening new positions too rapidly in the same asset.
- **Emotional Trading**: "Chasing" a move that has already matured.

### Solution: Hybrid Cooldown Model
The system uses a **Time + Price** logic to determine if a symbol is eligible for a new signal:

```text
48-hour cooldown window
↓
├─ During window: Check price movement relative to previous exit
│  ├─ Move >= 10%? → Allow trade (Escape Valve)
│  └─ Move < 10%? → Block trade (Cooldown Active)
│
└─ After 48h: Allow trade (Time window expired)
```

---

## Algorithm Details

### 1. Most Recent Exit Query
The engine queries Firestore for the most recent signal for the given symbol that attained an "exit" status (`TP1_HIT`, `TP2_HIT`, `TP3_HIT`, or `INVALIDATED`).

### 2. Status-Based Exit Level
To prevent the "Entry Price Bug" (measuring from entry instead of exit), the cooldown logic dynamically identifies the exact price level where the trade ended:
- **TP1_HIT**: Uses `take_profit_1`
- **TP2_HIT**: Uses `take_profit_2`
- **TP3_HIT**: Uses `take_profit_3`
- **INVALIDATED**: Uses `suggested_stop` (Stop-loss hit)

### 3. Price Move Calculation
The percentage change is calculated as:
`abs(current_price - exit_level) / exit_level * 100`

### 4. Decision Matrix
- **No Recent Exit**: Proceed with signal generation.
- **Exit > 48h ago**: Proceed with signal generation.
- **Exit < 48h ago AND Move >= 10%**: Proceed (High-volatility escape).
- **Exit < 48h ago AND Move < 10%**: **Block** (Cooldown active).

---

## Configuration

The cooldown behavior can be adjusted via `get_settings().COOLDOWN_SCOPE`:

| Scope | Behavior |
|-------|----------|
| `SYMBOL` | (Default) Blocks ALL patterns for that symbol if any exit happened. |
| `PATTERN`| Only blocks the SAME pattern (e.g., if BULL_FLAG exited, DOUBLE_BOTTOM is allowed). |

---

## Technical Infrastructure

### Firestore Composite Index
This feature requires a composite index to perform the status/timestamp/symbol query efficiently:

```yaml
Collection: live_signals (and test_signals)
Fields:
  - symbol (ASCENDING)
  - status (ASCENDING)
  - exit_time (DESCENDING)
```

### Dependency Injection
The `SignalGenerator` supports injecting a `SignalRepository`. For testing, always inject a mock to avoid `DefaultCredentialsError`.

---

## Usage Examples

### Integration in Engine
```python
def generate_signals(self, symbol: str):
    current_price = self.market_data.get_latest_price(symbol)

    # Check cooldown before expensive pattern analysis
    if self._is_in_cooldown(symbol, current_price):
        logger.info(f"[COOLDOWN] {symbol} is blocked.")
        return None

    # Proceed ...
```

### Manual Verification
You can check logs for `[COOLDOWN_ACTIVE]` or `[COOLDOWN_ESCAPE]` tags to audit the engine's decisions.
