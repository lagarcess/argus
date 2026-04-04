# Discord Threaded Signal Lifecycle

All signal lifecycle updates (TP hits, invalidations, expirations) are pinned to a single Discord thread.

## Architecture

![Signal Lifecycle Architecture](./images/signal-lifecycle-architecture.png)

## How It Works

### Thread Creation

1. `discord.send_signal()` is called with `?wait=true` to get the message ID
2. The message ID serves as the `thread_id` for Forum channels
3. This `thread_id` is saved to `signal.discord_thread_id`
4. The signal (with thread_id) is persisted to Firestore

### Lifecycle Updates

1. Signal is fetched from Firestore (includes `discord_thread_id`)
2. `discord.send_message()` is called with `thread_id=signal.discord_thread_id`
3. Discord routes the message to the existing thread using `?thread_id=`

### Self-Healing

If a signal lacks a `discord_thread_id` (due to initial notification failure):
1. System detects the missing thread_id during validation
2. A new thread is created via `discord.send_signal()`
3. The new thread_id is persisted for future updates

### Thread Recovery (Bot API)

For signals that may have threads but lost the reference, the system uses Discord's Bot API:

1. **On new signal creation**, before creating a new thread:
   - `discord.find_thread_by_signal_id()` searches active threads in the channel
   - Searches for threads containing `[signal_id]` in the thread name
   - If found, reuses the existing thread instead of creating a duplicate

2. **Requirements:**
   - `DISCORD_BOT_TOKEN` - Bot token with `READ_MESSAGE_HISTORY` permission
   - `DISCORD_CHANNEL_ID_CRYPTO` - Channel ID for crypto signals
   - `DISCORD_CHANNEL_ID_STOCK` - Channel ID for stock signals

3. **Channel Type Support:**
   - **Text Channels** - Uses channel-level `/threads/active` endpoint
   - **Forum Channels** - Uses guild-level `/guilds/{id}/threads/active` endpoint with parent filtering

> [!NOTE]
> Thread recovery is optional and gracefully degrades. If bot credentials are missing, the system falls back to creating new threads.

## Schema Fields

| Model | Field | Description |
|-------|-------|-------------|
| `Signal` | `discord_thread_id` | Links lifecycle updates to original broadcast |
| `Position` | `discord_thread_id` | Inherited from Signal on fill |
| `TradeExecution` | `discord_thread_id` | Propagated during archival for analytics |

## Webhook Routing

Messages are routed based on `TEST_MODE` and asset class:

| Scenario | Mode | Asset Class | Target Webhook |
| --- | --- | --- | --- |
| **Development/Tests** | `TEST_MODE=true` | Any | `TEST_DISCORD_WEBHOOK` |
| **Live Production** | `TEST_MODE=false` | `CRYPTO` | `LIVE_CRYPTO_DISCORD_WEBHOOK_URL` |
| **Live Production** | `TEST_MODE=false` | `EQUITY` | `LIVE_STOCK_DISCORD_WEBHOOK_URL` |
| **System Messages** | Any | None | `TEST_DISCORD_WEBHOOK` |

## Visual Testing

```powershell
# Ensure TEST_DISCORD_WEBHOOK is set in .env

# Test mode (default) - all messages go to test webhook
poetry run python scripts/visual_discord_test.py success      # Signal → TP1 → TP2 → TP3
poetry run python scripts/visual_discord_test.py invalidation # Signal → Invalidation
poetry run python scripts/visual_discord_test.py expiration   # Signal → Expiration
poetry run python scripts/visual_discord_test.py trail        # Runner trail path
poetry run python scripts/visual_discord_test.py all          # All paths

# Live mode - routes by asset class
poetry run python scripts/visual_discord_test.py all --mode live
```

| Path | Messages | Flow |
|------|----------|------|
| **Success** | 4 | Initial → TP1 → TP2 → TP3 |
| **Invalidation** | 2 | Initial → Invalidation |
| **Expiration** | 2 | Initial → Expiration |
| **Trail** | 5 | Initial → TP1 → Trail Updates → TP3 |
