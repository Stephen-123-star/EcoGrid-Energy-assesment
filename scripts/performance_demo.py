"""
EcoGrid Energy - Performance Benchmark Demonstration

Simulates high-volume event processing (1,500+ IoT smart meter readings)
through the decoupled EventBus, Marketplace matching engine, and SQLite persistence.
Measures total processing time, throughput (events/sec), and latency.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import time

# Ensure project root is on sys.path for direct script invocation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.event_bus import EventBus
from shared.models import EnergyDemandEvent
from smart_meter.simulator import SmartMeterSimulator
from marketplace.service import MarketplaceService
from settlement.service import SettlementService


async def run_performance_benchmark(meters: int = 30, readings_per_meter: int = 50) -> None:
    """
    Run high-volume benchmark and output performance metrics.
    Total events = meters * readings_per_meter (e.g. 30 * 50 = 1500 events).
    """
    total_target_readings = meters * readings_per_meter

    print("=" * 78)
    print(" ECOGRID ENERGY - PERFORMANCE BENCHMARK")
    print(f" Target Event Volume : {total_target_readings} Meter Reading Events ({meters} meters x {readings_per_meter} readings)")
    print("=" * 78)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        # Initialize components with minimal retry delay for high-throughput benchmarking
        bus = EventBus(max_retries=1, retry_delay=0.0)
        marketplace = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
        marketplace.register_subscriptions()

        settlement = SettlementService(event_bus=bus, database_path=tmp_db_path)
        settlement.register_subscriptions()

        # Seed substantial buyer demand (100 buyers with 20 kWh each = 2000 kWh demand)
        for i in range(100):
            await bus.publish(
                EnergyDemandEvent(
                    buyer_id=f"BYR-PERF-{i:03d}",
                    required_kwh=20.0,
                    maximum_price_per_kwh=0.30,
                    timestamp=datetime.now(timezone.utc),
                )
            )

        simulator = SmartMeterSimulator(
            event_bus=bus,
            meter_count=meters,
            readings_per_meter=readings_per_meter,
            delay_seconds=0.0,
            random_seed=1001,
        )

        print("\n[INFO] Starting high-frequency event ingestion benchmark...")
        start_time = time.perf_counter()

        await simulator.run_simulation()

        elapsed_time = time.perf_counter() - start_time
        events_per_sec = total_target_readings / max(elapsed_time, 0.0001)
        avg_latency_ms = (elapsed_time / total_target_readings) * 1000

        print("\n" + "=" * 78)
        print(" PERFORMANCE BENCHMARK RESULTS")
        print("=" * 78)
        print(f" Total Smart Meter Events Ingested : {simulator.total_readings_emitted}")
        print(f" Total Elapsed Processing Time     : {elapsed_time:.4f} seconds")
        print(f" Ingestion & Dispatch Throughput   : {events_per_sec:.2f} events/second")
        print(f" Mean Event Processing Latency     : {avg_latency_ms:.3f} ms / event")
        print("-" * 78)
        print(f" Total P2P Trades Matched          : {marketplace.total_trades_count}")
        print(f" Total Renewable Energy Traded     : {marketplace.total_energy_traded_kwh:.2f} kWh")
        print(f" Total Settlements Persisted (ACID): {settlement.get_settlement_count()}")
        print(f" Total Financial Ledger Value      : AUD ${settlement.get_total_settled_amount():.2f}")
        print("=" * 78)
        print(" Note: This local benchmark demonstrates non-blocking in-memory dispatch.")
        print(" In production, throughput would scale with clustered Kafka partitions.")
        print("=" * 78 + "\n")

    finally:
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)


if __name__ == "__main__":
    asyncio.run(run_performance_benchmark(meters=30, readings_per_meter=50))
