#!/usr/bin/env python
"""
Visual Discord Integration Test Script.

This script sends real payloads to a Discord webhook to visually verify
message threading and formatting across all signal lifecycle paths.

Usage:
    poetry run python scripts/visual_discord_test.py [PATH] [--mode test|live]

    Where [PATH] is one of:
    - success     : Signal → TP1 → TP2 → TP3 (full success path)
    - invalidation: Signal → Invalidation
    - expiration  : Signal → Expiration
    - trail       : Signal → TP1 → Trail Updates → TP3 (runner trail path)
    - short       : Short position trail path
    - patterns    : All 8 structural patterns with geometry verification
    - all         : Run all six paths (default)

    Modes:
    - test : Routes all traffic to TEST_DISCORD_WEBHOOK (default, safe)
    - live : Routes signals by asset class (CRYPTO → crypto webhook, EQUITY → stock webhook)

Examples:
    # Test mode (default) - all messages go to test webhook
    poetry run python scripts/visual_discord_test.py success

    # Live mode - routes to appropriate asset-class webhooks
    poetry run python scripts/visual_discord_test.py all --mode live
"""

import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

import typer
from dotenv import load_dotenv

# Setup: Load .env and add src to path BEFORE importing project modules
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Project imports (after path setup)  # noqa: E402
from crypto_signals.config import get_settings  # noqa: E402
from crypto_signals.domain.schemas import (  # noqa: E402
    AssetClass,
    OrderSide,
    Signal,
    SignalStatus,
    get_deterministic_id,
)
from crypto_signals.notifications.discord import DiscordClient  # noqa: E402

# Configuration
UPDATE_DELAY_SECONDS = 2.5  # Delay between updates for visual verification

# Typer app
app = typer.Typer(help="Visual Discord Integration Test Script")


class TestPath(str, Enum):
    """Available test paths."""

    success = "success"
    invalidation = "invalidation"
    expiration = "expiration"
    trail = "trail"
    short = "short"
    patterns = "patterns"  # 8 structural patterns with geometry
    shadow = "shadow"  # Shadow signal with rejection details
    harmonic = "harmonic"  # Harmonic pattern with ratio breakdown
    all = "all"


class Mode(str, Enum):
    """Environment mode for webhook routing."""

    test = "test"
    live = "live"


def create_test_signal(scenario: str) -> Signal:
    """Create a realistic test signal for visual verification."""
    now = datetime.now(timezone.utc)
    signal_key = f"{date.today()}|visual_test|BTC/USD|{scenario}"

    signal = Signal(
        signal_id=get_deterministic_id(signal_key),
        ds=date.today(),
        strategy_id="visual_test",
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        confluence_factors=["RSI_Divergence", "VCP_Compression", "Volume_Breakout"],
        entry_price=95000.00,
        pattern_name="bullish_engulfing",
        status=SignalStatus.WAITING,
        suggested_stop=91000.00,
        invalidation_price=92500.00,
        take_profit_1=98500.00,  # Conservative: +3.7%
        take_profit_2=102000.00,  # Structural: +7.4%
        take_profit_3=110000.00,  # Runner: +15.8%
        valid_until=now + timedelta(hours=24),
    )

    if scenario == "shadow":
        signal.pattern_name = "bull_flag"
        signal.pattern_classification = "MACRO_PATTERN"
        signal.pattern_duration_days = 95
        signal.status = SignalStatus.REJECTED_BY_FILTER
        signal.rejection_reason = "VOLUME 1.1X < 1.5X"
        signal.confluence_snapshot = {
            "rsi": 65,
            "adx": 30,
            "sma_trend": "Above",
            "volume_ratio": 1.1,
            "rr_ratio": 2.5,
        }

        def days_ago(d):
            return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat()

        signal.structural_anchors = [
            {"price": 95000, "timestamp": days_ago(95), "pivot_type": "peak", "index": 0},
            {
                "price": 85000,
                "timestamp": days_ago(45),
                "pivot_type": "valley",
                "index": 1,
            },
            {"price": 94000, "timestamp": days_ago(10), "pivot_type": "peak", "index": 2},
            {
                "price": 92000,
                "timestamp": days_ago(0),
                "pivot_type": "valley",
                "index": 3,
            },
        ]

    return signal


def create_structural_signal(
    pattern_name: str,
    pattern_duration_days: int,
    pattern_classification: str,
    structural_anchors: list[dict],
    symbol: str = "BTC/USD",
    entry_price: float = 95000.00,
) -> Signal:
    """Create a test signal with structural pattern metadata.

    Args:
        pattern_name: Pattern name (e.g., DOUBLE_BOTTOM)
        pattern_duration_days: Duration of pattern formation
        pattern_classification: STANDARD_PATTERN or MACRO_PATTERN
        structural_anchors: List of pivot dictionaries
        symbol: Trading symbol
        entry_price: Entry price for the signal
    """
    now = datetime.now(timezone.utc)
    signal_key = f"{date.today()}|visual_test|{symbol}|{pattern_name}"

    return Signal(
        signal_id=get_deterministic_id(signal_key),
        ds=date.today(),
        strategy_id="visual_test",
        symbol=symbol,
        asset_class=AssetClass.CRYPTO,
        confluence_factors=["RSI_Divergence", "Volume_Breakout"],
        entry_price=entry_price,
        pattern_name=pattern_name,
        status=SignalStatus.WAITING,
        suggested_stop=entry_price * 0.95,
        invalidation_price=entry_price * 0.96,
        take_profit_1=entry_price * 1.05,
        take_profit_2=entry_price * 1.10,
        take_profit_3=entry_price * 1.15,
        valid_until=now + timedelta(hours=24),
        # Structural metadata
        pattern_duration_days=pattern_duration_days,
        pattern_classification=pattern_classification,
        structural_anchors=structural_anchors,
    )


def test_success_path(client: DiscordClient) -> None:
    """
    Test the full success path: Signal → TP1 → TP2 → TP3.

    This simulates a trade that hits all three take-profit targets.
    """
    print("\n🚀 Starting SUCCESS PATH test...")
    print("-" * 50)

    signal = create_test_signal("success")

    # Step 1: Initial Signal Alert (creates thread)
    print("📤 Sending initial signal alert...")
    thread_id = client.send_signal(signal, thread_name="🧪 Visual Test: Success Path")

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    time.sleep(UPDATE_DELAY_SECONDS)

    # Step 2: TP1 Hit
    print("📤 Sending TP1 Hit update...")
    msg_tp1 = (
        "🎯 **SIGNAL UPDATE: BTC/USD** 🎯\n"
        "**Status**: TP1_HIT\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: TP1\n"
        "**Price Hit**: $98,500.00 (+3.7%)\n"
        "ℹ️ **Action**: Scaling Out (50%) & Stop -> **Breakeven**"
    )
    client.send_message(msg_tp1, thread_id=thread_id)
    print("✅ TP1 update sent")
    time.sleep(UPDATE_DELAY_SECONDS)

    # Step 3: TP2 Hit
    print("📤 Sending TP2 Hit update...")
    msg_tp2 = (
        "🚀 **SIGNAL UPDATE: BTC/USD** 🚀\n"
        "**Status**: TP2_HIT\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: TP2\n"
        "**Price Hit**: $102,000.00 (+7.4%)\n"
        "ℹ️ **Action**: Scaling Out (25%) & Trailing Stop Active"
    )
    client.send_message(msg_tp2, thread_id=thread_id)
    print("✅ TP2 update sent")
    time.sleep(UPDATE_DELAY_SECONDS)

    # Step 4: TP3 Hit (Runner Exit)
    print("📤 Sending TP3 Hit (Runner Exit) update...")
    msg_tp3 = (
        "🌕 **SIGNAL UPDATE: BTC/USD** 🌕\n"
        "**Status**: TP3_HIT\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: TP3 (Runner Target)\n"
        "**Price Hit**: $110,000.00 (+15.8%)\n"
        "🎉 **TRADE COMPLETE** - Full target achieved!"
    )
    client.send_message(msg_tp3, thread_id=thread_id)
    print("✅ TP3 (Runner Exit) update sent")

    print("-" * 50)
    print("✅ SUCCESS PATH test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Please verify in Discord that all 4 messages appear in the same thread.\n")


def test_invalidation_path(client: DiscordClient) -> None:
    """
    Test the invalidation path: Signal → Invalidation.

    This simulates a trade that gets invalidated due to structural breakdown.
    """
    print("\n🚫 Starting INVALIDATION PATH test...")
    print("-" * 50)

    signal = create_test_signal("invalidation")

    # Step 1: Initial Signal Alert (creates thread)
    print("📤 Sending initial signal alert...")
    thread_id = client.send_signal(
        signal, thread_name="🧪 Visual Test: Invalidation Path"
    )

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    time.sleep(UPDATE_DELAY_SECONDS)

    # Step 2: Invalidation
    print("📤 Sending invalidation update...")
    msg_invalidation = (
        "🚫 **SIGNAL UPDATE: BTC/USD** 🚫\n"
        "**Status**: INVALIDATED\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: STRUCTURAL_INVALIDATION\n"
        "**Invalidation Price**: $92,500.00\n"
        "⚠️ **Action**: Exit position immediately - Structure has broken down"
    )
    client.send_message(msg_invalidation, thread_id=thread_id)
    print("✅ Invalidation update sent")

    print("-" * 50)
    print("✅ INVALIDATION PATH test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Please verify in Discord that both messages appear in the same thread.\n")


def test_expiration_path(client: DiscordClient) -> None:
    """
    Test the expiration path: Signal → Expiration.

    This simulates a trade that expires after 24 hours without entry.
    """
    print("\n⏳ Starting EXPIRATION PATH test...")
    print("-" * 50)

    signal = create_test_signal("expiration")

    # Step 1: Initial Signal Alert (creates thread)
    print("📤 Sending initial signal alert...")
    thread_id = client.send_signal(signal, thread_name="🧪 Visual Test: Expiration Path")

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    time.sleep(UPDATE_DELAY_SECONDS)

    # Step 2: Expiration
    print("📤 Sending expiration update...")
    msg_expiration = (
        f"⏳ **SIGNAL EXPIRED: BTC/USD** ⏳\n"
        f"Signal from {date.today()} expired (24h Limit).\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Original Entry**: $95,000.00\n"
        "ℹ️ No action required - signal window has closed."
    )
    client.send_message(msg_expiration, thread_id=thread_id)
    print("✅ Expiration update sent")

    print("-" * 50)
    print("✅ EXPIRATION PATH test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Please verify in Discord that both messages appear in the same thread.\n")


def test_runner_trail_path(client: DiscordClient) -> None:
    """
    Test the runner trail path: Signal → TP1 → Trail Updates → TP3.

    This simulates a trade where the trailing stop (Chandelier Exit) moves
    multiple times during the Runner phase, testing:
    - Thread integrity: All updates stay in the same thread
    - Formatting: "New vs. Previous" price context is readable
    - Threshold respect: <1% moves are logged but not sent to Discord
    """
    print("\n🌕 Starting RUNNER TRAIL PATH test...")
    print("-" * 50)

    signal = create_test_signal("trail")
    # Entry: $95,000 | TP1: $98,500 | TP2: $102,000
    # Initial trailing stop should be above entry once in Runner phase
    # Scenario: Price rallied to ~$100K, Chandelier Exit calculates to $96,000
    signal.take_profit_3 = 96000.00

    # Step 1: Initial Signal Alert (creates thread)
    print("📤 Step 1: Sending initial signal alert...")
    thread_id = client.send_signal(
        signal, thread_name="🧪 Visual Test: Runner Trail Path"
    )

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    signal.discord_thread_id = thread_id  # Attach for subsequent updates
    # Track last NOTIFIED value for UX continuity (Option B)
    last_notified_stop = signal.take_profit_3
    time.sleep(3)  # Longer delay for visual verification

    # Step 2: TP1 Hit - Start of Runner phase
    print("📤 Step 2: Sending TP1 Hit (Runner phase begins)...")
    signal.status = SignalStatus.TP1_HIT
    msg_tp1 = (
        "🎯 **SIGNAL UPDATE: BTC/USD** 🎯\n"
        "**Status**: TP1_HIT\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: TP1\n"
        "**Price Hit**: $98,500.00 (+3.7%)\n"
        "ℹ️ **Action**: Scaling Out (50%) & Stop → **Breakeven** ($95,000)\n"
        f"🏃📈 **Runner Phase Active** - Trailing stop now at ${signal.take_profit_3:,.2f}"
    )
    client.send_message(msg_tp1, thread_id=thread_id)
    print("✅ TP1 update sent - Runner phase started")
    time.sleep(3)

    # Step 3: Significant Move (>1%) - $96,000 → $99,000 (+3.1%)
    # Price continued to rally, Chandelier Exit moved up
    print("📤 Step 3: Sending SIGNIFICANT trail update ($96,000 → $99,000)...")
    signal.take_profit_3 = 99000.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(f"   Movement: {movement_pct:.1f}% (>1% threshold → sends notification)")
    client.send_trail_update(signal, old_stop=last_notified_stop)
    last_notified_stop = signal.take_profit_3  # Update last notified
    print("✅ Significant trail update sent")
    time.sleep(3)

    # Step 4: Minor Move (<1%) - $99,000 → $99,500 (+0.5%)
    print("📤 Step 4: Simulating MINOR trail update ($99,000 → $99,500)...")
    signal.take_profit_3 = 99500.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(
        f"   Movement: {movement_pct:.2f}% (<1% threshold → skipping Discord notification)"
    )
    print(f"   ℹ️  Local state updated: take_profit_3 = ${signal.take_profit_3:,.2f}")
    print(f"   ℹ️  Last notified value stays at: ${last_notified_stop:,.2f}")
    print("   ⏭️  No Discord message sent (threshold not met)")
    time.sleep(3)

    # Step 5: Another Significant Move (>1%) - $99,000 → $103,000 (+4.0%)
    # Note: Using last_notified_stop ($99,000) for display, not actual previous ($99,500)
    print("📤 Step 5: Sending SIGNIFICANT trail update ($99,000 → $103,000)...")
    signal.take_profit_3 = 103000.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(
        f"   Movement from last notified: {movement_pct:.1f}% (>1% → sends notification)"
    )
    client.send_trail_update(signal, old_stop=last_notified_stop)
    last_notified_stop = signal.take_profit_3  # Update last notified
    print("✅ Significant trail update sent")
    time.sleep(3)

    # Step 6: Final TP3 Exit (Chandelier Exit triggered)
    # Price pulled back and closed below the trailing stop
    print("📤 Step 6: Sending TP3 Hit (Runner Exit)...")
    signal.status = SignalStatus.TP3_HIT
    msg_tp3 = (
        "🏃📈 **SIGNAL UPDATE: BTC/USD** 🏃📈\n"
        "**Status**: TP3_HIT\n"
        "**Pattern**: BULLISH ENGULFING\n"
        "**Reason**: TP_HIT (Chandelier Exit)\n"
        f"**Exit Price**: ~${signal.take_profit_3:,.2f} (+8.4% from entry)\n"
        "🎉 **RUNNER COMPLETE** - Profit locked via dynamic trailing!"
    )
    client.send_message(msg_tp3, thread_id=thread_id)
    print("✅ TP3 (Runner Exit) update sent")

    print("-" * 50)
    print("✅ RUNNER TRAIL PATH test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Expected messages in thread: 5 (Initial + TP1 + 2 Trail + TP3)")
    print(
        "   Note: Step 4 was skipped but Discord shows continuous values ($96K→$99K→$103K)"
    )
    print("   Please verify in Discord that all messages appear in the same thread.\n")


def test_short_runner_trail_path(client: DiscordClient) -> None:
    """
    Test the SHORT runner trail path: Signal → TP1 → Trail Updates → TP3.

    This simulates a SHORT position where the trailing stop (Chandelier Exit)
    moves DOWNWARD as price falls, testing:
    - Thread integrity: All updates stay in the same thread
    - Directional trailing: Stop moves DOWN (not up) for shorts
    - Threshold respect: <1% moves are logged but not sent to Discord
    """
    print("\n🔻 Starting SHORT RUNNER TRAIL PATH test...")
    print("-" * 50)

    signal = create_test_signal("short_trail")
    # Override for Short position scenario
    signal.side = OrderSide.SELL
    signal.entry_price = 65000.00
    signal.take_profit_1 = 62000.00  # TP1 for short is BELOW entry
    signal.take_profit_2 = 59000.00
    signal.take_profit_3 = 64000.00  # Initial trailing stop (above current price)
    signal.suggested_stop = 67000.00  # Stop loss for short is ABOVE entry
    signal.invalidation_price = 66500.00

    # Step 1: Initial Signal Alert (creates thread)
    print("📤 Step 1: Sending initial SHORT signal alert...")
    thread_id = client.send_signal(
        signal, thread_name="🧪 Visual Test: Short Runner Trail Path"
    )

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    signal.discord_thread_id = thread_id
    # Track last NOTIFIED value for UX continuity (Option B)
    last_notified_stop = signal.take_profit_3
    time.sleep(3)

    # Step 2: TP1 Hit - Start of Runner phase
    print("📤 Step 2: Sending TP1 Hit (Runner phase begins)...")
    signal.status = SignalStatus.TP1_HIT
    msg_tp1 = (
        "🎯 **SIGNAL UPDATE: BTC/USD** 🎯\n"
        "**Side**: SHORT 🔻\n"
        "**Status**: TP1_HIT\n"
        "**Pattern**: BULLISH ENGULFING (Reversal Play)\n"
        "**Price Hit**: $62,000.00 (-4.6%)\n"
        "ℹ️ **Action**: Scaling Out (50%) & Stop → **Breakeven** ($65,000)\n"
        f"🏃📉 **Runner Phase Active** - Trailing stop now at ${signal.take_profit_3:,.2f}"
    )
    client.send_message(msg_tp1, thread_id=thread_id)
    print("✅ TP1 update sent - Runner phase started")
    time.sleep(3)

    # Step 3: Significant Move (>1%) - $64,000 → $62,000 (-3.1%)
    # For shorts, trailing stop moves DOWN as price falls
    print("📤 Step 3: Sending SIGNIFICANT trail update ($64,000 → $62,000)...")
    signal.take_profit_3 = 62000.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(f"   Movement: {movement_pct:.1f}% (>1% threshold → sends notification)")
    client.send_trail_update(signal, old_stop=last_notified_stop)
    last_notified_stop = signal.take_profit_3  # Update last notified
    print("✅ Significant trail update sent")
    time.sleep(3)

    # Step 4: Minor Move (<1%) - $62,000 → $61,800 (-0.3%)
    print("📤 Step 4: Simulating MINOR trail update ($62,000 → $61,800)...")
    signal.take_profit_3 = 61800.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(
        f"   Movement: {movement_pct:.2f}% (<1% threshold → skipping Discord notification)"
    )
    print(f"   ℹ️  Local state updated: take_profit_3 = ${signal.take_profit_3:,.2f}")
    print(f"   ℹ️  Last notified value stays at: ${last_notified_stop:,.2f}")
    print("   ⏭️  No Discord message sent (threshold not met)")
    time.sleep(3)

    # Step 5: Another Significant Move (>1%) - $62,000 → $60,000 (-3.2%)
    # Note: Using last_notified_stop ($62,000) for display, not actual previous ($61,800)
    print("📤 Step 5: Sending SIGNIFICANT trail update ($62,000 → $60,000)...")
    signal.take_profit_3 = 60000.00
    movement_pct = (
        abs((signal.take_profit_3 - last_notified_stop) / last_notified_stop) * 100
    )
    print(
        f"   Movement from last notified: {movement_pct:.1f}% (>1% → sends notification)"
    )
    client.send_trail_update(signal, old_stop=last_notified_stop)
    last_notified_stop = signal.take_profit_3  # Update last notified
    print("✅ Significant trail update sent")
    time.sleep(3)

    # Step 6: Final TP3 Exit (price bounced above trailing stop)
    print("📤 Step 6: Sending TP3 Hit (Runner Exit)...")
    signal.status = SignalStatus.TP3_HIT
    msg_tp3 = (
        "🏃📉 **SIGNAL UPDATE: BTC/USD** 🏃📉\n"
        "**Side**: SHORT\n"
        "**Status**: TP3_HIT\n"
        "**Reason**: TP_HIT (Chandelier Exit)\n"
        f"**Exit Price**: ~${signal.take_profit_3:,.2f} (-7.7% from entry)\n"
        "🎉 **SHORT RUNNER COMPLETE** - Profit locked via downward trailing!"
    )
    client.send_message(msg_tp3, thread_id=thread_id)
    print("✅ TP3 (Runner Exit) update sent")

    print("-" * 50)
    print("✅ SHORT RUNNER TRAIL PATH test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Expected messages in thread: 5 (Initial + TP1 + 2 Trail + TP3)")
    print(
        "   Note: Step 4 was skipped but Discord shows continuous values ($64K→$62K→$60K)"
    )
    print("   Trailing stop moved DOWN as price fell.\n")


def test_structural_patterns(client: DiscordClient) -> None:
    """
    Test all 8 multi-day structural patterns with geometry verification.

    Verifies:
    - MACRO header (🏛️) for patterns >90 days
    - Formation Scale line with duration and classification
    - Pattern Geometry block with "Days Ago" calculations
    - Pivot anchor formatting for each pattern shape
    """
    print("\n📐 Starting STRUCTURAL PATTERNS test...")
    print("-" * 50)
    print("Testing 8 multi-day patterns with geometry visualization\n")

    # Calculate reference dates (for realistic "days ago" values)
    today = date.today()

    def days_ago(n: int) -> str:
        """Return ISO date string for n days ago."""
        return str(today - timedelta(days=n))

    # =========================================================================
    # PATTERN DEFINITIONS
    # Each pattern has realistic geometry based on technical analysis standards
    # =========================================================================

    patterns = [
        # 1. DOUBLE BOTTOM - Standard (W-shape: Valley, Peak, Valley)
        {
            "name": "DOUBLE_BOTTOM",
            "symbol": "BTC/USD",
            "entry": 45000.00,
            "duration": 42,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 38500.00,
                    "timestamp": days_ago(42),
                    "pivot_type": "valley",
                    "index": 0,
                },
                {
                    "price": 43200.00,
                    "timestamp": days_ago(21),
                    "pivot_type": "peak",
                    "index": 1,
                },
                {
                    "price": 38800.00,
                    "timestamp": days_ago(7),
                    "pivot_type": "valley",
                    "index": 2,
                },
            ],
            "description": "Classic W-shape with ~0.8% valley variance",
        },
        # 2. INVERSE HEAD & SHOULDERS - MACRO (5 pivots: symmetrical pattern)
        {
            "name": "INVERSE_HEAD_SHOULDERS",
            "symbol": "ETH/USD",
            "entry": 3800.00,
            "duration": 112,
            "classification": "MACRO_PATTERN",
            "anchors": [
                {
                    "price": 2850.00,
                    "timestamp": days_ago(112),
                    "pivot_type": "valley",
                    "index": 0,
                },  # Left Shoulder
                {
                    "price": 3200.00,
                    "timestamp": days_ago(84),
                    "pivot_type": "peak",
                    "index": 1,
                },  # Neckline 1
                {
                    "price": 2600.00,
                    "timestamp": days_ago(56),
                    "pivot_type": "valley",
                    "index": 2,
                },  # Head (lowest)
                {
                    "price": 3250.00,
                    "timestamp": days_ago(28),
                    "pivot_type": "peak",
                    "index": 3,
                },  # Neckline 2
                {
                    "price": 2900.00,
                    "timestamp": days_ago(7),
                    "pivot_type": "valley",
                    "index": 4,
                },  # Right Shoulder
            ],
            "description": "Institutional-scale reversal with 5-pivot symmetry",
        },
        # 3. BULL FLAG - Standard (Pole + Flag consolidation)
        {
            "name": "BULL_FLAG",
            "symbol": "SOL/USD",
            "entry": 125.00,
            "duration": 18,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 95.00,
                    "timestamp": days_ago(18),
                    "pivot_type": "valley",
                    "index": 0,
                },  # Pole base
                {
                    "price": 130.00,
                    "timestamp": days_ago(10),
                    "pivot_type": "peak",
                    "index": 1,
                },  # Pole top
                {
                    "price": 118.00,
                    "timestamp": days_ago(5),
                    "pivot_type": "valley",
                    "index": 2,
                },  # Flag low
                {
                    "price": 126.00,
                    "timestamp": days_ago(2),
                    "pivot_type": "peak",
                    "index": 3,
                },  # Flag high
            ],
            "description": "Strong 36% pole with tight flag retracement",
        },
        # 4. CUP AND HANDLE - MACRO (U-shape with handle)
        {
            "name": "CUP_AND_HANDLE",
            "symbol": "AAPL",
            "entry": 195.00,
            "duration": 95,
            "classification": "MACRO_PATTERN",
            "anchors": [
                {
                    "price": 182.00,
                    "timestamp": days_ago(95),
                    "pivot_type": "peak",
                    "index": 0,
                },  # Cup left rim
                {
                    "price": 165.00,
                    "timestamp": days_ago(60),
                    "pivot_type": "valley",
                    "index": 1,
                },  # Cup bottom
                {
                    "price": 184.00,
                    "timestamp": days_ago(30),
                    "pivot_type": "peak",
                    "index": 2,
                },  # Cup right rim
                {
                    "price": 178.00,
                    "timestamp": days_ago(10),
                    "pivot_type": "valley",
                    "index": 3,
                },  # Handle low
            ],
            "description": "Rounded base with shallow handle pullback",
        },
        # 5. ASCENDING TRIANGLE - Standard (Flat resistance, rising lows)
        {
            "name": "ASCENDING_TRIANGLE",
            "symbol": "NVDA",
            "entry": 145.00,
            "duration": 35,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 128.00,
                    "timestamp": days_ago(35),
                    "pivot_type": "valley",
                    "index": 0,
                },  # First low
                {
                    "price": 142.00,
                    "timestamp": days_ago(28),
                    "pivot_type": "peak",
                    "index": 1,
                },  # Resistance test 1
                {
                    "price": 133.00,
                    "timestamp": days_ago(21),
                    "pivot_type": "valley",
                    "index": 2,
                },  # Higher low 1
                {
                    "price": 143.00,
                    "timestamp": days_ago(14),
                    "pivot_type": "peak",
                    "index": 3,
                },  # Resistance test 2
                {
                    "price": 138.00,
                    "timestamp": days_ago(5),
                    "pivot_type": "valley",
                    "index": 4,
                },  # Higher low 2
            ],
            "description": "Coiling pattern with rising demand",
        },
        # 6. FALLING WEDGE - Standard (Convergent, declining channel)
        {
            "name": "FALLING_WEDGE",
            "symbol": "TSLA",
            "entry": 265.00,
            "duration": 28,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 310.00,
                    "timestamp": days_ago(28),
                    "pivot_type": "peak",
                    "index": 0,
                },  # Upper trendline start
                {
                    "price": 275.00,
                    "timestamp": days_ago(21),
                    "pivot_type": "valley",
                    "index": 1,
                },  # Lower trendline 1
                {
                    "price": 295.00,
                    "timestamp": days_ago(14),
                    "pivot_type": "peak",
                    "index": 2,
                },  # Upper trendline 2
                {
                    "price": 258.00,
                    "timestamp": days_ago(3),
                    "pivot_type": "valley",
                    "index": 3,
                },  # Lower trendline 2
            ],
            "description": "Bullish reversal wedge with volume divergence",
        },
        # 7. RISING THREE METHODS - Standard (Candlestick continuation)
        {
            "name": "RISING_THREE_METHODS",
            "symbol": "AMZN",
            "entry": 188.00,
            "duration": 8,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 178.00,
                    "timestamp": days_ago(8),
                    "pivot_type": "valley",
                    "index": 0,
                },  # Pre-pattern low
                {
                    "price": 185.00,
                    "timestamp": days_ago(5),
                    "pivot_type": "peak",
                    "index": 1,
                },  # Strong bull candle
                {
                    "price": 182.00,
                    "timestamp": days_ago(2),
                    "pivot_type": "valley",
                    "index": 2,
                },  # Consolidation low
            ],
            "description": "5-candle continuation with contained retracement",
        },
        # 8. TWEEZER BOTTOMS - Standard (Equal lows candlestick pattern)
        {
            "name": "TWEEZER_BOTTOMS",
            "symbol": "GOOGL",
            "entry": 178.00,
            "duration": 5,
            "classification": "STANDARD_PATTERN",
            "anchors": [
                {
                    "price": 172.50,
                    "timestamp": days_ago(5),
                    "pivot_type": "valley",
                    "index": 0,
                },  # First bottom
                {
                    "price": 176.00,
                    "timestamp": days_ago(3),
                    "pivot_type": "peak",
                    "index": 1,
                },  # Interim high
                {
                    "price": 172.55,
                    "timestamp": days_ago(1),
                    "pivot_type": "valley",
                    "index": 2,
                },  # Second bottom (matched)
            ],
            "description": "Matched lows with <0.1% variance indicate strong support",
        },
    ]

    # =========================================================================
    # SEND EACH PATTERN TO DISCORD
    # =========================================================================

    for idx, pattern_config in enumerate(patterns, 1):
        print(
            f"\n📤 Pattern {idx}/8: {pattern_config['name']} ({pattern_config['classification']})"
        )

        signal = create_structural_signal(
            pattern_name=pattern_config["name"],
            pattern_duration_days=pattern_config["duration"],
            pattern_classification=pattern_config["classification"],
            structural_anchors=pattern_config["anchors"],
            symbol=pattern_config["symbol"],
            entry_price=pattern_config["entry"],
        )

        # Create thread name with MACRO indicator if applicable
        is_macro = pattern_config["classification"] == "MACRO_PATTERN"
        macro_badge = "🏛️ " if is_macro else ""
        thread_name = (
            f"🧪 {macro_badge}{pattern_config['name'].replace('_', ' ').title()}"
        )

        # Send signal (creates thread with Pattern Geometry block)
        thread_id = client.send_signal(signal, thread_name=thread_name)

        if thread_id:
            print(f"   ✅ Thread created: {thread_id}")
            print(f"      Duration: {pattern_config['duration']} days")
            print(f"      Anchors: {len(pattern_config['anchors'])} pivots")
            print(f"      {pattern_config['description']}")
        else:
            print(f"   ❌ FAILED: Could not create thread for {pattern_config['name']}")

        # Rate limiting between patterns
        time.sleep(UPDATE_DELAY_SECONDS)

    print("\n" + "-" * 50)
    print("✅ STRUCTURAL PATTERNS test complete!")
    print("\n   Verification Checklist:")
    print("   □ MACRO patterns show 🏛️ [MACRO SETUP] header")
    print("   □ All patterns have 'Formation Scale' line")
    print("   □ Pattern Geometry shows correct 'Days Ago'")
    print("   □ Pivots are listed chronologically (oldest → newest)")
    print("   □ Inverse H&S shows 5 pivots with symmetry")
    print("\n   Please verify in Discord that all 8 threads display correctly.\n")


def test_shadow_path(client: DiscordClient) -> None:
    """Test Shadow Signal (Rejected) notification."""
    print("Testing SHADOW SIGNAL Path (Rejected by Filter)...")

    # Create manually triggered shadow signal
    signal = create_test_signal("shadow")

    # Send shadow notification
    client.send_shadow_signal(signal)

    print("✅ Shadow Signal Sent")
    print(f"   Reason: {signal.rejection_reason}")
    print(f"   Snapshot: {signal.confluence_snapshot}")
    print("   Verify: Ghost emoji 👻, Grey Embed, [REJECTED] Header")


def test_harmonic_alert(client: DiscordClient) -> None:
    """Test Harmonic Pattern alert with Ratio Breakdown.

    This simulates a perfect Bat pattern on BTC with harmonic metadata
    displayed in the Discord message.
    """
    print("\n🦇 Starting HARMONIC PATTERN test (Bat)...")
    print("-" * 50)

    now = datetime.now(timezone.utc)
    signal_key = f"{date.today()}|visual_test|BTC/USD|harmonic_bat"

    # Create a Bat pattern signal with harmonic metadata
    signal = Signal(
        signal_id=get_deterministic_id(signal_key),
        ds=date.today(),
        strategy_id="visual_test_harmonic",
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        confluence_factors=["Harmonic_Bat", "Fibonacci_Confluence"],
        entry_price=95000.00,
        pattern_name="BAT",
        status=SignalStatus.WAITING,
        suggested_stop=91000.00,
        invalidation_price=92500.00,
        take_profit_1=98500.00,
        take_profit_2=102000.00,
        take_profit_3=110000.00,
        valid_until=now + timedelta(hours=24),
        # Harmonic metadata for Bat pattern
        # Bat: B at 0.45 (0.382-0.50 range), D at 0.886
        harmonic_metadata={
            "B_ratio": 0.450,  # 45% retracement of XA
            "D_ratio": 0.886,  # 88.6% retracement of XA
        },
    )

    # Send the signal
    print("📤 Sending Bat pattern signal with harmonic ratios...")
    thread_id = client.send_signal(signal, thread_name="🧪 Visual Test: Bat Pattern")

    if not thread_id:
        print("❌ FAILED: Could not create thread (send_signal returned None)")
        return

    print(f"✅ Thread created: {thread_id}")
    print("\n   Expected Discord output:")
    print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("   🚀 **BAT** detected on **BTC/USD**")
    print("   ")
    print("   **Entry Price:** $95,000.00")
    print("   **Stop Loss:** $91,000.00")
    print("   **Take Profit 1 (Conservative):** $98,500.00")
    print("   **Take Profit 2 (Structural):** $102,000.00")
    print("   **Take Profit 3 (Runner):** $110,000.00")
    print("   ")
    print("   📐 **Ratio Breakdown**")
    print("   B-Leg: 45.0% | D-Leg: 88.6%")
    print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("\n" + "-" * 50)
    print("✅ HARMONIC PATTERN test complete!")
    print(f"   Thread ID: {thread_id}")
    print("   Please verify in Discord that the Ratio Breakdown appears correctly.\n")


def run_all_tests(client: DiscordClient) -> None:
    """Run all seven test paths."""
    test_success_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_invalidation_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_expiration_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_runner_trail_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_short_runner_trail_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_structural_patterns(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_shadow_path(client)
    print("\n" + "=" * 70 + "\n")
    time.sleep(1)

    test_harmonic_alert(client)


@app.command()
def main(
    path: Annotated[
        TestPath,
        typer.Argument(help="Test path to run"),
    ] = TestPath.all,
    mode: Annotated[
        Mode,
        typer.Option(
            "--mode",
            "-m",
            help="Routing mode: 'test' routes all to TEST_DISCORD_WEBHOOK, 'live' routes by asset class",
        ),
    ] = Mode.test,
) -> None:
    """Run visual Discord integration tests."""
    print("\n" + "=" * 70)
    print("  VISUAL DISCORD INTEGRATION TEST")
    print("  Testing Threaded Signal Lifecycle Messages")
    print("=" * 70)

    # Create settings with appropriate TEST_MODE based on --mode flag
    settings = get_settings()

    if mode == Mode.live:
        # Force live mode (override TEST_MODE)
        # Note: This requires LIVE_CRYPTO_DISCORD_WEBHOOK_URL and LIVE_STOCK_DISCORD_WEBHOOK_URL
        # to be set in environment or .env
        settings.TEST_MODE = False
        print("\n⚠️  Mode: LIVE - Routing by asset class")
        print("   CRYPTO signals → LIVE_CRYPTO_DISCORD_WEBHOOK_URL")
        print("   EQUITY signals → LIVE_STOCK_DISCORD_WEBHOOK_URL")
        print("   System messages → TEST_DISCORD_WEBHOOK")
    else:
        print("\n🧪 Mode: TEST - All traffic routes to TEST_DISCORD_WEBHOOK")

    # Initialize client with settings
    client = DiscordClient(settings=settings)

    print(f"⏱️  Update delay: {UPDATE_DELAY_SECONDS}s between messages\n")

    # Run the selected test path
    if path == TestPath.success:
        test_success_path(client)
    elif path == TestPath.invalidation:
        test_invalidation_path(client)
    elif path == TestPath.expiration:
        test_expiration_path(client)
    elif path == TestPath.trail:
        test_runner_trail_path(client)
    elif path == TestPath.short:
        test_short_runner_trail_path(client)
    elif path == TestPath.patterns:
        test_structural_patterns(client)
    elif path == TestPath.shadow:
        test_shadow_path(client)
    elif path == TestPath.harmonic:
        test_harmonic_alert(client)
    elif path == TestPath.all:
        run_all_tests(client)

    print("\n" + "=" * 70)
    print("  VISUAL VERIFICATION COMPLETE")
    print("  Please check your Discord channel to verify threading and formatting.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    app()
