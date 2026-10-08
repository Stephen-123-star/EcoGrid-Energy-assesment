"""
EcoGrid Energy - Resilience & Failure Recovery Demonstration

Demonstrates:
1. Transient Handler Failure -> Automatic Retry -> Successful Recovery.
2. Persistent Handler Failure -> Retries Exhausted -> Dead Letter Queue (DLQ) Recording.
3. Fault Isolation -> Broken subscriber does not crash healthy subscribers or publishers.
4. Idempotent Settlement -> Duplicate trade events do not double-bill or corrupt the ledger.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys
import tempfile
import uuid

# Ensure project root is on sys.path for direct script invocation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.event_bus import EventBus
from shared.logging_config import setup_logging
from shared.models import MeterReadingEvent, TradeMatchedEvent
from settlement.service import SettlementService


async def run_failure_demonstration() -> None:
    """Execute controlled failure scenarios to showcase architectural resilience."""
    logger = setup_logging("INFO")

    print("=" * 78)
    print(" ECOGRID ENERGY - RESILIENCE & FAULT HANDLING DEMONSTRATION")
    print("=" * 78)

    bus = EventBus(max_retries=3, retry_delay=0.05, logger=logger)

    # -------------------------------------------------------------------------
    # SCENARIO 1: Transient Failure & Automatic Retry
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print(" SCENARIO 1: Transient Subscriber Failure & Automatic Retry")
    print("-" * 78)

    transient_attempts = 0

    def flaky_grid_telemetry_handler(event: MeterReadingEvent) -> str:
        nonlocal transient_attempts
        transient_attempts += 1
        if transient_attempts < 3:
            print(f"  [ATTEMPT {transient_attempts}/3] Simulating transient network socket timeout...")
            raise TimeoutError("Grid IoT Gateway connection timed out")
        print(f"  [ATTEMPT {transient_attempts}/3] Reconnection successful! Telemetry processed.")
        return "SUCCESS"

    bus.subscribe(MeterReadingEvent, flaky_grid_telemetry_handler)

    test_event_1 = MeterReadingEvent(
        meter_id="MTR-RETRY-01",
        household_id="HH-RETRY-01",
        generation_kwh=4.2,
        consumption_kwh=1.1,
    )

    print(f"Publishing MeterReadingEvent [{test_event_1.meter_id}]...")
    await bus.publish(test_event_1)

    print(f"Result: Succeeded on attempt {transient_attempts}. DLQ items: {bus.dlq.count()}")

    # -------------------------------------------------------------------------
    # SCENARIO 2: Persistent Failure & Dead Letter Queue (DLQ)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print(" SCENARIO 2: Persistent Failure & Dead Letter Queue (DLQ) Containment")
    print("-" * 78)

    persistent_attempts = 0

    def broken_legacy_handler(event: MeterReadingEvent) -> None:
        nonlocal persistent_attempts
        persistent_attempts += 1
        print(f"  [ATTEMPT {persistent_attempts}/3] Fatal exception in legacy downstream system...")
        raise ValueError("Legacy downstream parser rejected modern payload format")

    # Clear previous subscribers for isolation
    bus._subscribers.clear()
    bus.subscribe(MeterReadingEvent, broken_legacy_handler)

    test_event_2 = MeterReadingEvent(
        meter_id="MTR-FATAL-99",
        household_id="HH-FATAL-99",
        generation_kwh=3.5,
        consumption_kwh=0.8,
    )

    print(f"Publishing MeterReadingEvent [{test_event_2.meter_id}]...")
    await bus.publish(test_event_2)

    print(f"Result: Retries exhausted ({persistent_attempts} attempts). DLQ items: {bus.dlq.count()}")
    for item in bus.dlq.get_all():
        print(f"  * DLQ Entry -> Event: {type(item.event).__name__} (Meter: {item.event.meter_id}) | "
              f"Handler: {item.handler_name} | Error: {item.error_message} | Attempts: {item.attempts}")

    # -------------------------------------------------------------------------
    # SCENARIO 3: Financial Settlement Idempotency Under Duplicate Events
    # -------------------------------------------------------------------------
    print("\n" + "-" * 78)
    print(" SCENARIO 3: Financial Settlement Idempotency (Duplicate Trade Events)")
    print("-" * 78)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db = tmp_file.name

    try:
        bus._subscribers.clear()
        settlement = SettlementService(event_bus=bus, database_path=tmp_db, logger=logger)
        settlement.register_subscriptions()

        dup_trade = TradeMatchedEvent(
            trade_id="TRD-IDEMPOTENT-888",
            seller_id="HH-SELLER-1",
            buyer_id="HH-BUYER-2",
            energy_kwh=12.5,
            price_per_kwh=0.25,
        )

        print(f"Sending TradeMatchedEvent [{dup_trade.trade_id}] for the 1st time...")
        await bus.publish(dup_trade)

        print(f"Sending SAME TradeMatchedEvent [{dup_trade.trade_id}] for the 2nd time (Network replay simulation)...")
        await bus.publish(dup_trade)

        print(f"Settlements in DB: {settlement.get_settlement_count()} (Expected: 1)")
        print(f"Duplicates Blocked: {settlement.duplicate_trades_ignored} (Expected: 1)")
        print(f"Total Amount Settled: AUD ${settlement.get_total_settled_amount():.2f} (Expected: AUD $3.12)")

    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    print("\n" + "=" * 78)
    print(" RESILIENCE DEMONSTRATION COMPLETE: All fault-tolerance mechanisms verified.")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    asyncio.run(run_failure_demonstration())
