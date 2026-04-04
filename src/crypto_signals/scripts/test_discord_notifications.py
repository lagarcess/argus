"""
Visual Test Script for Discord Notifications.

Run this to send sample notifications to your Discord webhook for visual testing.
This sends REAL messages to Discord - use in TEST_MODE with your test webhook.

Usage: poetry run python -m crypto_signals.scripts.test_discord_notifications

Why this exists:
- tests/test_mock_notifications.py = Unit tests with MOCKS (for CI/CD, no real messages)
- This script = Integration test with REAL Discord messages (for visual verification)

This script covers all notification types:
1. New Signal (with all targets)
2. Trail Update (long with directional arrow)
3. Signal Update - TP1_HIT (with scaling out action)
4. Trade Close - Win (💰)
5. Signal Update - INVALIDATED
6. Signal Update - EXPIRED
7. Trade Close - Loss (💀)
"""

from datetime import date, datetime, timezone

from crypto_signals.domain.schemas import (
    AssetClass,
    ExitReason,
    OrderSide,
    Position,
    Signal,
    SignalStatus,
    TradeStatus,
)
from crypto_signals.notifications.discord import DiscordClient
from crypto_signals.secrets_manager import init_secrets

print("🔔 Discord Notification Visual Test")
print("=" * 50)

# Initialize secrets so webhook URLs are available
print("Loading secrets...")
init_secrets()

discord = DiscordClient()

# Get test_label for display (same logic as production)
test_label = "[TEST] " if discord.settings.TEST_MODE else "[LIVE] "
print(f"\n📋 Mode: {test_label.strip()}")


# =============================================================================
# SCENARIO 1: LONG TRADE LIFECYCLE (Win Path - TP1 Hit)
# =============================================================================
print("\n" + "=" * 50)
print("📈 SCENARIO 1: LONG TRADE WIN PATH (TP1 Hit)")
print("=" * 50)

# Step 1a: New Signal
print("\n1️⃣  Sending NEW SIGNAL (Long BTC/USD)...")
long_signal = Signal(
    signal_id="visual-test-long-001",
    ds=date.today(),
    strategy_id="visual_test",
    symbol="BTC/USD",
    asset_class=AssetClass.CRYPTO,
    entry_price=98500.0,
    pattern_name="BULLISH_ENGULFING",
    suggested_stop=95000.0,
    take_profit_1=102000.0,
    take_profit_2=108000.0,
    take_profit_3=115000.0,
    invalidation_price=94000.0,
    side=OrderSide.BUY,
    status=SignalStatus.WAITING,
)
thread_id = discord.send_signal(long_signal, thread_name="📊 Visual Test - BTC/USD Long")
if thread_id:
    print(f"   ✅ Sent! Thread ID: {thread_id}")
    long_signal.discord_thread_id = thread_id
else:
    print("   ❌ Failed to send signal")
    exit(1)

# Step 1b: Trail Update
print("\n2️⃣  Sending TRAIL UPDATE (Stop moved up)...")
long_signal.take_profit_3 = 98000.0  # Moved trailing stop up
result: bool | str = discord.send_trail_update(
    signal=long_signal,
    old_stop=95000.0,
    asset_class=AssetClass.CRYPTO,
)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")

# Step 1c: Signal Update - TP1 Hit (using new method)
print("\n3️⃣  Sending SIGNAL UPDATE (TP1 Hit + Scaling Out)...")
long_signal.status = SignalStatus.TP1_HIT
long_signal.exit_reason = ExitReason.TP1
result = discord.send_signal_update(long_signal)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")

# Step 1d: Trade Close - Win
print("\n4️⃣  Sending TRADE CLOSED - WIN (💰 TP Hit)...")
win_position = Position(
    position_id="visual-test-long-001",
    ds=date.today(),
    account_id="paper",
    symbol="BTC/USD",
    signal_id="visual-test-long-001",
    status=TradeStatus.CLOSED,
    entry_fill_price=98500.0,
    current_stop_loss=98500.0,  # At breakeven
    qty=0.025,  # Half position after scaling out
    side=OrderSide.BUY,
    exit_fill_price=102000.0,
    exit_time=datetime.now(timezone.utc),
    filled_at=datetime(2025, 12, 23, 14, 0, 0, tzinfo=timezone.utc),
)
result = discord.send_trade_close(
    signal=long_signal,
    position=win_position,
    pnl_usd=87.50,
    pnl_pct=3.55,
    duration_str="9h 15m",
    exit_reason="Take Profit 1",
)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")


# =============================================================================
# SCENARIO 2: SHORT TRADE LIFECYCLE (Invalidation Path)
# =============================================================================
print("\n" + "=" * 50)
print("📉 SCENARIO 2: SHORT TRADE INVALIDATION PATH")
print("=" * 50)

# Step 2a: New Signal (Short)
print("\n5️⃣  Sending NEW SIGNAL (Short ETH/USD)...")
short_signal = Signal(
    signal_id="visual-test-short-002",
    ds=date.today(),
    strategy_id="visual_test",
    symbol="ETH/USD",
    asset_class=AssetClass.CRYPTO,
    entry_price=3500.0,
    pattern_name="BEARISH_ENGULFING",
    suggested_stop=3600.0,
    take_profit_1=3300.0,
    take_profit_2=3100.0,
    invalidation_price=3650.0,
    side=OrderSide.SELL,
    status=SignalStatus.WAITING,
)
thread_id_2 = discord.send_signal(
    short_signal, thread_name="📊 Visual Test - ETH/USD Short"
)
if thread_id_2:
    print(f"   ✅ Sent! Thread ID: {thread_id_2}")
    short_signal.discord_thread_id = thread_id_2
else:
    print("   ❌ Failed to send signal")

# Step 2b: Signal Invalidated (using new method)
print("\n6️⃣  Sending SIGNAL UPDATE (Invalidated)...")
short_signal.status = SignalStatus.INVALIDATED
short_signal.exit_reason = ExitReason.STRUCTURAL_INVALIDATION
result = discord.send_signal_update(short_signal)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")


# =============================================================================
# SCENARIO 3: TRADE EXPIRATION PATH
# =============================================================================
print("\n" + "=" * 50)
print("⏳ SCENARIO 3: SIGNAL EXPIRATION PATH")
print("=" * 50)

# Step 3a: New Signal
print("\n7️⃣  Sending NEW SIGNAL (SOL/USD)...")
expired_signal = Signal(
    signal_id="visual-test-expired-003",
    ds=date.today(),
    strategy_id="visual_test",
    symbol="SOL/USD",
    asset_class=AssetClass.CRYPTO,
    entry_price=180.0,
    pattern_name="BULLISH_FLAG",
    suggested_stop=170.0,
    take_profit_1=195.0,
    take_profit_2=210.0,
    side=OrderSide.BUY,
    status=SignalStatus.WAITING,
)
thread_id_3 = discord.send_signal(expired_signal, thread_name="📊 Visual Test - SOL/USD")
if thread_id_3:
    print(f"   ✅ Sent! Thread ID: {thread_id_3}")
    expired_signal.discord_thread_id = thread_id_3
else:
    print("   ❌ Failed to send signal")

# Step 3b: Signal Expired (using new method)
print("\n8️⃣  Sending SIGNAL UPDATE (Expired - Time Decay)...")
expired_signal.status = SignalStatus.EXPIRED
expired_signal.exit_reason = ExitReason.EXPIRED
result = discord.send_signal_update(expired_signal)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")


# =============================================================================
# SCENARIO 4: STOP LOSS HIT (Loss Path)
# =============================================================================
print("\n" + "=" * 50)
print("💀 SCENARIO 4: STOP LOSS HIT (Loss Path)")
print("=" * 50)

# Step 4a: New Signal
print("\n9️⃣  Sending NEW SIGNAL (DOGE/USD)...")
loss_signal = Signal(
    signal_id="visual-test-loss-004",
    ds=date.today(),
    strategy_id="visual_test",
    symbol="DOGE/USD",
    asset_class=AssetClass.CRYPTO,
    entry_price=0.32,
    pattern_name="BULLISH_HARAMI",
    suggested_stop=0.30,
    take_profit_1=0.36,
    take_profit_2=0.40,
    side=OrderSide.BUY,
    status=SignalStatus.WAITING,
)
thread_id_4 = discord.send_signal(loss_signal, thread_name="📊 Visual Test - DOGE/USD")
if thread_id_4:
    print(f"   ✅ Sent! Thread ID: {thread_id_4}")
    loss_signal.discord_thread_id = thread_id_4
else:
    print("   ❌ Failed to send signal")

# Step 4b: Trade Close - Loss (Stop Loss Hit)
print("\n🔟 Sending TRADE CLOSED - LOSS (💀 Stop Loss Hit)...")
loss_position = Position(
    position_id="visual-test-loss-004",
    ds=date.today(),
    account_id="paper",
    symbol="DOGE/USD",
    signal_id="visual-test-loss-004",
    status=TradeStatus.CLOSED,
    entry_fill_price=0.32,
    current_stop_loss=0.30,
    qty=1000.0,
    side=OrderSide.BUY,
    exit_fill_price=0.30,
    exit_time=datetime.now(timezone.utc),
    filled_at=datetime(2025, 12, 23, 20, 30, 0, tzinfo=timezone.utc),
)
result = discord.send_trade_close(
    signal=loss_signal,
    position=loss_position,
    pnl_usd=-20.0,
    pnl_pct=-6.25,
    duration_str="2h 45m",
    exit_reason="Stop Loss",
)
print(f"   {'✅ Sent!' if result else '❌ Failed'}")


# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 50)
print("✅ Visual test complete! Check your Discord channel.")
print("=" * 50)
print("\nYou should see 4 threads:")
print("   1️⃣  BTC/USD Long: Signal → Trail → TP1 Hit (scaling out) → Win Close (💰)")
print("   2️⃣  ETH/USD Short: Signal → Invalidated (🚫)")
print("   3️⃣  SOL/USD: Signal → Expired (⏳)")
print("   4️⃣  DOGE/USD: Signal → Stop Loss Hit → Loss Close (💀)")
