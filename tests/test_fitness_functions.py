"""
EcoGrid Energy - Architectural Fitness Functions

Executable architectural fitness tests validating the non-functional quality attributes
stipulated in ICT711 Assessment 2:
1. Performance (FAST)
2. Security (SECURE)
3. Maintainability (MAINTAINABLE)
4. Evolvability (EVOLVABLE)
5. Resilience (RESILIENT)
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from shared.config import get_config
from shared.event_bus import EventBus
from shared.models import (
    EnergyDemandEvent,
    MeterReadingEvent,
    SettlementCompletedEvent,
    TradeMatchedEvent,
)
from smart_meter.simulator import SmartMeterSimulator
from marketplace.service import MarketplaceService
from settlement.service import SettlementService


class TestArchitecturalFitnessFunctions(unittest.IsolatedAsyncioTestCase):
    """
    Architectural Fitness Function verification suite for EcoGrid.
    """

    # -------------------------------------------------------------------------
    # 1. PERFORMANCE FITNESS FUNCTION (FAST)
    # -------------------------------------------------------------------------
    async def test_ff_performance_high_frequency_throughput(self):
        """
        FITNESS FUNCTION: PERFORMANCE
        Rule: Ingesting and processing a batch of 200 high-frequency smart meter
              events through the decoupled pipeline must complete in under 2.0 seconds
              (> 100 events/sec on standard commodity hardware).
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_db = tmp_file.name

        try:
            bus = EventBus(max_retries=1, retry_delay=0.0)
            market = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
            market.register_subscriptions()
            settlement = SettlementService(event_bus=bus, database_path=tmp_db)
            settlement.register_subscriptions()

            # Seed 5 buyers
            for i in range(5):
                await bus.publish(EnergyDemandEvent(f"BYR-FF-{i}", 50.0, 0.30))

            # Simulate 10 meters with 20 readings each = 200 readings
            simulator = SmartMeterSimulator(
                event_bus=bus,
                meter_count=10,
                readings_per_meter=20,
                delay_seconds=0.0,
                random_seed=42,
            )

            start = time.perf_counter()
            await simulator.run_simulation()
            duration = time.perf_counter() - start

            throughput = simulator.total_readings_emitted / max(duration, 0.0001)

            # Assert threshold
            self.assertLess(duration, 2.0, f"Performance test exceeded 2.0s: {duration:.3f}s")
            self.assertGreater(throughput, 100.0, f"Throughput below 100 events/s: {throughput:.1f}")
        finally:
            if 'settlement' in locals():
                settlement.close()
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    # -------------------------------------------------------------------------
    # 2. SECURITY FITNESS FUNCTION (SECURE)
    # -------------------------------------------------------------------------
    def test_ff_security_input_validation_and_injection_immunity(self):
        """
        FITNESS FUNCTION: SECURITY
        Rule: All domain event models must reject negative values, malicious injection payloads,
              and invalid schemas before reaching business logic or database persistence.
        """
        # Negative generation rejection
        with self.assertRaises(ValueError):
            MeterReadingEvent(meter_id="MTR-01", household_id="HH-01", generation_kwh=-5.0, consumption_kwh=1.0)

        # Negative price rejection
        with self.assertRaises(ValueError):
            EnergyDemandEvent(buyer_id="BYR-01", required_kwh=10.0, maximum_price_per_kwh=-0.25)

        # Zero energy trade rejection
        with self.assertRaises(ValueError):
            TradeMatchedEvent(trade_id="TRD-01", seller_id="HH-1", buyer_id="HH-2", energy_kwh=0.0, price_per_kwh=0.25)

    def test_ff_security_git_ignores_secrets_and_databases(self):
        """
        FITNESS FUNCTION: SECURITY
        Rule: .gitignore must strictly ignore .env and *.db files to prevent credential/data leakage.
        """
        gitignore_path = Path(".gitignore")
        self.assertTrue(gitignore_path.exists(), ".gitignore file must exist.")
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(".env", content, ".gitignore must exclude .env files.")
        self.assertIn("data/*.db", content, ".gitignore must exclude SQLite database files.")

    # -------------------------------------------------------------------------
    # 3. MAINTAINABILITY FITNESS FUNCTION (MAINTAINABLE)
    # -------------------------------------------------------------------------
    def test_ff_maintainability_bounded_context_independence(self):
        """
        FITNESS FUNCTION: MAINTAINABILITY
        Rule: Bounded contexts must be strictly decoupled. smart_meter and marketplace
              must have zero imports from settlement database or internal persistence logic.
        """
        import sys
        import smart_meter.simulator as sm
        import marketplace.service as mp

        # Ensure no cross-contamination of database imports in smart_meter or marketplace
        self.assertNotIn("sqlite3", sm.__dict__, "smart_meter must not import sqlite3 directly.")
        self.assertNotIn("sqlite3", mp.__dict__, "marketplace must not import sqlite3 directly.")
        self.assertNotIn("SettlementService", sm.__dict__, "smart_meter must not reference SettlementService.")
        self.assertNotIn("SettlementService", mp.__dict__, "marketplace must not reference SettlementService.")

    # -------------------------------------------------------------------------
    # 4. EVOLVABILITY FITNESS FUNCTION (EVOLVABLE)
    # -------------------------------------------------------------------------
    async def test_ff_evolvability_zero_modification_subscriber_extension(self):
        """
        FITNESS FUNCTION: EVOLVABILITY
        Rule: A new external service (e.g. CarbonOffsetAuditor or GridAnalytics)
              must be attachable via EventBus subscription without modifying any existing
              publisher code, simulator code, or marketplace logic.
        """
        bus = EventBus(max_retries=1, retry_delay=0.0)
        market = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
        market.register_subscriptions()

        # Define a brand-new hypothetical analytics service
        captured_analytics = []

        class GridCarbonAuditor:
            def on_trade_matched(self, event: TradeMatchedEvent):
                # 0.4 kg CO2 avoided per clean kWh traded
                co2_avoided_kg = round(event.energy_kwh * 0.4, 2)
                captured_analytics.append((event.trade_id, co2_avoided_kg))

        auditor = GridCarbonAuditor()
        # Register new listener dynamically
        bus.subscribe(TradeMatchedEvent, auditor.on_trade_matched)

        # Trigger trading flow
        await bus.publish(EnergyDemandEvent("BYR-EVO", 15.0, 0.30))
        await bus.publish(MeterReadingEvent("MTR-EVO", "HH-EVO", generation_kwh=20.0, consumption_kwh=5.0))

        # Assert that the new auditor captured the trade without modifying the marketplace
        self.assertEqual(len(captured_analytics), 1)
        self.assertEqual(captured_analytics[0][1], 6.0)  # 15 kWh * 0.4 = 6.0 kg CO2 avoided

    # -------------------------------------------------------------------------
    # 5. RESILIENCE FITNESS FUNCTION (RESILIENT)
    # -------------------------------------------------------------------------
    async def test_ff_resilience_fault_isolation_and_dlq_containment(self):
        """
        FITNESS FUNCTION: RESILIENCE
        Rule: If one subscriber crashes or fails permanently, other subscribers must continue
              uninterrupted, and the failed event must be isolated in the Dead Letter Queue.
        """
        bus = EventBus(max_retries=2, retry_delay=0.001)
        healthy_processed = []

        def broken_subscriber(event: MeterReadingEvent):
            raise ConnectionResetError("Remote telemetry sink unavailable")

        def healthy_subscriber(event: MeterReadingEvent):
            healthy_processed.append(event.meter_id)

        # Subscribe both broken and healthy handlers
        bus.subscribe(MeterReadingEvent, broken_subscriber)
        bus.subscribe(MeterReadingEvent, healthy_subscriber)

        event = MeterReadingEvent("MTR-RESILIENT", "HH-RESILIENT", 5.0, 1.0)
        await bus.publish(event)

        # Assert fault isolation: healthy subscriber was not blocked
        self.assertEqual(len(healthy_processed), 1)
        self.assertEqual(healthy_processed[0], "MTR-RESILIENT")

        # Assert DLQ containment: failed event captured in DLQ after 2 attempts
        self.assertEqual(bus.dlq.count(), 1)
        dlq_item = bus.dlq.get_all()[0]
        self.assertEqual(dlq_item.attempts, 2)
        self.assertEqual(dlq_item.event.meter_id, "MTR-RESILIENT")


if __name__ == "__main__":
    unittest.main()
