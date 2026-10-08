"""
EcoGrid Energy - Comprehensive Unit & Integration Test Suite

Tests all core requirements:
A. Domain model validation test
B. Meter surplus calculation test
C. Event Bus publish/subscribe test
D. Marketplace matching test
E. Marketplace cannot oversell energy test
F. Settlement calculation test
G. Settlement database persistence test
H. Settlement idempotency test
I. Failure/retry test
J. Dead Letter Queue test
K. End-to-end integration test
L. Context separation/import sanity test
"""

import asyncio
from datetime import datetime, timezone
import os
import sqlite3
import tempfile
import unittest
import uuid

from shared.event_bus import EventBus, DeadLetterItem
from shared.models import (
    EnergyDemandEvent,
    MeterReadingEvent,
    SettlementCompletedEvent,
    TradeMatchedEvent,
)
from smart_meter.simulator import SmartMeterSimulator
from marketplace.service import MarketplaceService
from settlement.service import SettlementService


class TestEcoGridSystem(unittest.IsolatedAsyncioTestCase):
    """System and unit test suite for EcoGrid Energy platform."""

    # -------------------------------------------------------------------------
    # A. Domain Model Validation Test
    # -------------------------------------------------------------------------
    def test_domain_model_validation(self):
        """Test valid domain event creation and rejection of invalid values."""
        # Valid events
        valid_meter = MeterReadingEvent("M-1", "H-1", 4.5, 1.2)
        self.assertEqual(valid_meter.meter_id, "M-1")
        self.assertEqual(valid_meter.generation_kwh, 4.5)

        valid_demand = EnergyDemandEvent("B-1", 10.0, 0.30)
        self.assertEqual(valid_demand.buyer_id, "B-1")
        self.assertEqual(valid_demand.required_kwh, 10.0)

        valid_trade = TradeMatchedEvent("T-1", "H-1", "B-1", 5.0, 0.25)
        self.assertEqual(valid_trade.total_amount, 1.25)

        # Invalid MeterReadingEvent (negative generation)
        with self.assertRaises(ValueError):
            MeterReadingEvent("M-1", "H-1", -1.0, 1.0)

        # Invalid MeterReadingEvent (negative consumption)
        with self.assertRaises(ValueError):
            MeterReadingEvent("M-1", "H-1", 1.0, -0.5)

        # Invalid EnergyDemandEvent (zero or negative kWh)
        with self.assertRaises(ValueError):
            EnergyDemandEvent("B-1", 0.0, 0.30)

        # Invalid EnergyDemandEvent (negative price)
        with self.assertRaises(ValueError):
            EnergyDemandEvent("B-1", 5.0, -0.10)

        # Invalid TradeMatchedEvent (negative price)
        with self.assertRaises(ValueError):
            TradeMatchedEvent("T-1", "H-1", "B-1", 5.0, -0.25)

        # Invalid TradeMatchedEvent (empty trade_id)
        with self.assertRaises(ValueError):
            TradeMatchedEvent("", "H-1", "B-1", 5.0, 0.25)

    # -------------------------------------------------------------------------
    # B. Meter Surplus Calculation Test
    # -------------------------------------------------------------------------
    def test_meter_surplus_calculation(self):
        """Test accurate calculation of surplus solar energy."""
        # Generation exceeds consumption -> surplus
        reading_surplus = MeterReadingEvent("M-1", "H-1", generation_kwh=5.5, consumption_kwh=2.1)
        self.assertEqual(reading_surplus.surplus_kwh, 3.4)

        # Consumption exceeds generation -> zero surplus
        reading_deficit = MeterReadingEvent("M-2", "H-2", generation_kwh=1.0, consumption_kwh=3.5)
        self.assertEqual(reading_deficit.surplus_kwh, 0.0)

        # Zero generation -> zero surplus
        reading_zero = MeterReadingEvent("M-3", "H-3", generation_kwh=0.0, consumption_kwh=2.0)
        self.assertEqual(reading_zero.surplus_kwh, 0.0)

    # -------------------------------------------------------------------------
    # C. Event Bus Publish/Subscribe Test
    # -------------------------------------------------------------------------
    async def test_event_bus_pub_sub(self):
        """Test sync and async event handlers and subscriber isolation."""
        bus = EventBus(max_retries=1, retry_delay=0.0)
        received_sync = []
        received_async = []

        def sync_handler(event: MeterReadingEvent):
            received_sync.append(event)

        async def async_handler(event: MeterReadingEvent):
            received_async.append(event)

        bus.subscribe(MeterReadingEvent, sync_handler)
        bus.subscribe(MeterReadingEvent, async_handler)

        self.assertEqual(bus.subscriber_count(MeterReadingEvent), 2)

        event = MeterReadingEvent("M-1", "H-1", 3.0, 1.0)
        invoked = await bus.publish(event)

        self.assertEqual(invoked, 2)
        self.assertEqual(len(received_sync), 1)
        self.assertEqual(len(received_async), 1)
        self.assertEqual(received_sync[0].meter_id, "M-1")
        self.assertEqual(received_async[0].meter_id, "M-1")

    # -------------------------------------------------------------------------
    # D. Marketplace Matching Test
    # -------------------------------------------------------------------------
    async def test_marketplace_matching(self):
        """Test price-compatible FIFO matching algorithm."""
        bus = EventBus()
        market = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
        market.register_subscriptions()

        # Buyer demands 10 kWh @ max 0.30 AUD/kWh
        demand = EnergyDemandEvent("BUYER-A", 10.0, 0.30)
        await bus.publish(demand)

        # Seller offers 10 kWh surplus
        seller_meter = MeterReadingEvent("MTR-1", "SELLER-1", generation_kwh=12.0, consumption_kwh=2.0)
        await bus.publish(seller_meter)

        self.assertEqual(market.total_trades_count, 1)
        self.assertEqual(market.total_energy_traded_kwh, 10.0)
        trade = market.matched_trades[0]
        self.assertEqual(trade.seller_id, "SELLER-1")
        self.assertEqual(trade.buyer_id, "BUYER-A")
        self.assertEqual(trade.energy_kwh, 10.0)
        self.assertEqual(trade.price_per_kwh, 0.25)
        self.assertEqual(trade.total_amount, 2.50)

    # -------------------------------------------------------------------------
    # E. Marketplace Cannot Oversell Energy Test
    # -------------------------------------------------------------------------
    async def test_marketplace_no_overselling(self):
        """Test that market strictly respects available supply and never oversells."""
        bus = EventBus()
        market = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
        market.register_subscriptions()

        # Seller generates 5.0 kWh surplus
        seller_meter = MeterReadingEvent("MTR-1", "SELLER-1", generation_kwh=6.0, consumption_kwh=1.0)
        await bus.publish(seller_meter)

        # Buyer 1 requests 3.0 kWh
        await bus.publish(EnergyDemandEvent("BUYER-1", 3.0, 0.30))
        self.assertEqual(market.total_energy_traded_kwh, 3.0)
        self.assertEqual(market.pending_supply_kwh, 2.0)

        # Buyer 2 requests 4.0 kWh (only 2.0 kWh left in seller supply)
        await bus.publish(EnergyDemandEvent("BUYER-2", 4.0, 0.30))
        self.assertEqual(market.total_energy_traded_kwh, 5.0)
        self.assertEqual(market.pending_supply_kwh, 0.0)
        self.assertEqual(market.pending_demand_kwh, 2.0)  # 2 kWh unmet demand

    # -------------------------------------------------------------------------
    # F. Settlement Calculation Test
    # -------------------------------------------------------------------------
    def test_settlement_calculation(self):
        """Test exact calculation of settlement monetary amounts."""
        trade = TradeMatchedEvent(
            trade_id="TRD-TEST-1",
            seller_id="HH-1",
            buyer_id="HH-2",
            energy_kwh=14.5,
            price_per_kwh=0.25,
        )
        self.assertEqual(trade.total_amount, 3.62)

    # -------------------------------------------------------------------------
    # G. Settlement Database Persistence Test
    # -------------------------------------------------------------------------
    async def test_settlement_db_persistence(self):
        """Test SQLite persistence of settlements using an isolated temp database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_db_path = tmp_file.name

        try:
            bus = EventBus()
            settlement = SettlementService(event_bus=bus, database_path=tmp_db_path)
            settlement.register_subscriptions()

            trade = TradeMatchedEvent("TRD-P01", "SELLER-1", "BUYER-1", 10.0, 0.25)
            await bus.publish(trade)

            record = settlement.get_settlement_by_trade_id("TRD-P01")
            self.assertIsNotNone(record)
            self.assertEqual(record["trade_id"], "TRD-P01")
            self.assertEqual(record["seller_id"], "SELLER-1")
            self.assertEqual(record["buyer_id"], "BUYER-1")
            self.assertEqual(record["energy_kwh"], 10.0)
            self.assertEqual(record["price_per_kwh"], 0.25)
            self.assertEqual(record["total_amount"], 2.50)
            self.assertEqual(record["status"], "SETTLED")
            self.assertEqual(settlement.get_settlement_count(), 1)
        finally:
            if 'settlement' in locals():
                settlement.close()
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

    # -------------------------------------------------------------------------
    # H. Settlement Idempotency Test
    # -------------------------------------------------------------------------
    async def test_settlement_idempotency(self):
        """Test that duplicate trade events do not duplicate database records."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_db_path = tmp_file.name

        try:
            bus = EventBus()
            settlement = SettlementService(event_bus=bus, database_path=tmp_db_path)
            settlement.register_subscriptions()

            trade = TradeMatchedEvent("TRD-DUP-01", "SELLER-1", "BUYER-1", 8.0, 0.25)

            # Publish same trade event twice
            await bus.publish(trade)
            await bus.publish(trade)

            self.assertEqual(settlement.get_settlement_count(), 1)
            self.assertEqual(settlement.duplicate_trades_ignored, 1)
            self.assertEqual(settlement.get_total_settled_amount(), 2.00)
        finally:
            if 'settlement' in locals():
                settlement.close()
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

    # -------------------------------------------------------------------------
    # I. Failure / Retry Test
    # -------------------------------------------------------------------------
    async def test_event_bus_retry_mechanism(self):
        """Test that transient handler failures are retried and eventually succeed."""
        bus = EventBus(max_retries=3, retry_delay=0.001)
        attempts = 0

        def flaky_handler(event: MeterReadingEvent):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionError("Simulated temporary network glitch")
            return "OK"

        bus.subscribe(MeterReadingEvent, flaky_handler)
        event = MeterReadingEvent("M-1", "H-1", 3.0, 1.0)
        await bus.publish(event)

        self.assertEqual(attempts, 3)
        self.assertEqual(bus.dlq.count(), 0)  # Succeeded on 3rd attempt, not in DLQ

    # -------------------------------------------------------------------------
    # J. Dead Letter Queue Test
    # -------------------------------------------------------------------------
    async def test_dead_letter_queue(self):
        """Test that persistent failures exhaust retries and are sent to DLQ."""
        bus = EventBus(max_retries=3, retry_delay=0.001)

        def fatal_handler(event: MeterReadingEvent):
            raise RuntimeError("Permanent database corrupt error")

        bus.subscribe(MeterReadingEvent, fatal_handler)
        event = MeterReadingEvent("M-FATAL", "H-FATAL", 4.0, 1.0)
        await bus.publish(event)

        self.assertEqual(bus.dlq.count(), 1)
        dlq_item: DeadLetterItem = bus.dlq.get_all()[0]
        self.assertEqual(dlq_item.event.meter_id, "M-FATAL")
        self.assertEqual(dlq_item.attempts, 3)
        self.assertIn("Permanent database corrupt error", dlq_item.error_message)

    # -------------------------------------------------------------------------
    # K. End-to-End Integration Test
    # -------------------------------------------------------------------------
    async def test_end_to_end_flow(self):
        """Test end-to-end event chain: Smart Meter -> EventBus -> Market -> EventBus -> Settlement -> SQLite."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_db_path = tmp_file.name

        try:
            bus = EventBus()
            market = MarketplaceService(event_bus=bus, default_price_per_kwh=0.25)
            market.register_subscriptions()

            settlement = SettlementService(event_bus=bus, database_path=tmp_db_path)
            settlement.register_subscriptions()

            # 1. Register buyer demand for 20 kWh
            await bus.publish(EnergyDemandEvent("BUYER-E2E", 20.0, 0.30))

            # 2. Run smart meter simulation with 5 meters, 2 readings each
            simulator = SmartMeterSimulator(
                event_bus=bus,
                meter_count=5,
                readings_per_meter=2,
                delay_seconds=0.0,
                random_seed=123,
            )
            await simulator.run_simulation()

            # Verify that trades were created and persisted
            settlements = settlement.get_all_settlements()
            self.assertGreater(len(settlements), 0)
            self.assertGreater(settlement.get_total_settled_amount(), 0.0)
            self.assertEqual(market.total_trades_count, len(settlements))
        finally:
            if 'settlement' in locals():
                settlement.close()
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

    # -------------------------------------------------------------------------
    # L. Context Separation / Import Sanity Test
    # -------------------------------------------------------------------------
    def test_bounded_context_isolation(self):
        """Ensure bounded contexts do not violate DDD boundaries or cross-import internal services."""
        import smart_meter.simulator as sm_mod
        import marketplace.service as mp_mod
        import settlement.service as st_mod

        # smart_meter must not import marketplace or settlement
        self.assertFalse(hasattr(sm_mod, "MarketplaceService"))
        self.assertFalse(hasattr(sm_mod, "SettlementService"))

        # marketplace must not import settlement persistence or smart meter simulator
        self.assertFalse(hasattr(mp_mod, "SettlementService"))
        self.assertFalse(hasattr(mp_mod, "SmartMeterSimulator"))

        # settlement must not import marketplace service or smart meter simulator
        self.assertFalse(hasattr(st_mod, "MarketplaceService"))
        self.assertFalse(hasattr(st_mod, "SmartMeterSimulator"))


if __name__ == "__main__":
    unittest.main()
