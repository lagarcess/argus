# Position Management & TP Automation

Automatic position sizing and stop-loss management when take-profit targets are hit.

## Scaling Strategy

| Stage       | Scale Out        | Remaining | Stop Moves To       |
| ----------- | ---------------- | --------- | ------------------- |
| **Entry**   | -                | 100%      | Initial SL          |
| **TP1 Hit** | 50%              | 50%       | Breakeven (entry)   |
| **TP2 Hit** | 50% of remaining | 25%       | TP1 level           |
| **TP3 Hit** | Runner exits     | 0%        | TP2 level (trailed) |

## How It Works

When `ENABLE_EXECUTION=True`, the system automatically manages positions:

### Take-Profit Stages

1. **TP1 Detected** → Sells 50%, moves stop to breakeven
2. **TP2 Detected** → Sells 50% of remaining (25% total), moves stop to TP1
3. **TP3 Detected** → Closes runner position completely

### Active Trailing (Chandelier Exit)

When price moves favorably during Runner phase:

- Chandelier Exit is recalculated each day
- If new stop > current stop → Alpaca order is modified
- Discord notified if movement > 1%

### Exit Triggers

| Trigger          | Alpaca Action            |
| ---------------- | ------------------------ |
| **TP3 Hit**      | Close remaining position |
| **Invalidation** | Emergency close          |
| **Expiration**   | Auto-cancel (no action)  |

## Schema Tracking Fields

| Field               | Description                             |
| ------------------- | --------------------------------------- |
| `original_qty`      | Quantity before any scale-outs          |
| `scaled_out_qty`    | Cumulative quantity sold                |
| `scaled_out_price`  | Fill price of the most recent scale-out |
| `scaled_out_at`     | Timestamp of the most recent scale-out  |
| `breakeven_applied` | Whether stop moved to breakeven         |

## Discord Notifications

Each TP level sends an update with action hints:

- **TP1**: "ℹ️ Scaling Out (50%) & Stop -> Breakeven"
- **TP2**: "ℹ️ Scaling Out (50% remaining) & Stop -> TP1"
- **TP3**: "🏃 Runner Complete - Trailing stop hit"

## Configuration

```env
# Required for automated execution
ENABLE_EXECUTION=true
ALPACA_PAPER_TRADING=true  # Safety guard

# Position sizing
RISK_PER_TRADE=100.0  # Fixed dollar risk per trade
```

## Exit Price Capture (Issue #141)

### Problem

Volatile markets can leave orders in "Accepted" or "Partially Filled" states when the system checks immediately after order submission. This causes:

- ❌ $0.00 exit prices in BigQuery (missing exit fills)
- ❌ Broken P&L calculations (negative fees instead of profit)
- ❌ Orphaned positions (awaiting backfill indefinitely)

### Solution: Retry Budget + Deferred Backfill

Each exit (emergency close, scale-out) now has a configurable retry budget:

```python
# Attempt 1: Immediate fill check
if order.filled_avg_price:
    position.exit_fill_price = order.filled_avg_price  # ✅ Success

# Attempts 2-3: Retry with 1.5s delay between retries
else:
    result = engine._retry_fill_price_capture(order_id, max_retries=3)
    if result:
        position.exit_fill_price = result[0]  # ✅ Caught on retry
    else:
        position.awaiting_backfill = True  # 📋 Deferred to sync_position_status()
```

### Weighted Average for Multi-Stage Exits

When scaling out in multiple stages (TP1 @ $100, TP2 @ $110):

- **TP1**: `scaled_out_price = 100.0`
- **TP2**: `scaled_out_price = (50% × $100 + 50% × $110) / 100% = $105.00` (weighted average)
- **BigQuery**: `exit_price = $105.00` for accurate P&L

```python
# Weighted average formula
previous_value = scaled_out_qty × scaled_out_price  # Value from TP1
new_value = scale_qty × fill_price                  # Value from TP2
total_value = previous_value + new_value
new_average = total_value / (scaled_out_qty + scale_qty)
```

### Backfill Pipeline

**PricePatchPipeline** runs daily to repair $0.00 exit prices:

1. Query BigQuery: `WHERE exit_price = 0.0 AND exit_order_id IS NOT NULL`
2. Fetch actual fill price from Alpaca Orders API
3. Update BigQuery with actual price + finalized flag

Cron: `0 1 * * *` (1 AM UTC daily) — runs before signal generation to ensure clean data.

### Tracking Fields

| Field                    | Description                                                            |
| ------------------------ | ---------------------------------------------------------------------- |
| `exit_fill_price`        | Actual fill price (immediate or via retry/backfill)                    |
| `exit_order_id`          | Alpaca order ID for exit order reconciliation                          |
| `scaled_out_prices`      | Array of scale-out records: `{qty, price, timestamp, order_id}`        |
| `awaiting_backfill`      | Flag: True if retry budget exhausted, pending `sync_position_status()` |
| `trade_duration_seconds` | Time from entry to exit (calculated on close)                          |

## Data Life Cycle (Self-Cleaning)

To maintain database hygiene and manage storage costs, positions have a fixed **90-day physical lifecycle**:

- **Mechanism**: The `delete_at` field is automatically set to `now + 90 days` upon position creation.
- **TTL Enforcement**: Google Cloud Firestore automatically prunes expired positions via the `delete_at` TTL policy.
- **Manual Cleanup**: The `cleanup_firestore.py` script can be used to manually trigger pruning across all operational collections.

## Related Files

- [`execution.py`](../src/crypto_signals/engine/execution.py) - `scale_out_position()`, `move_stop_to_breakeven()`
- [`main.py`](../src/crypto_signals/main.py) - TP automation logic
- [`schemas.py`](../src/crypto_signals/domain/schemas.py) - Position tracking fields
