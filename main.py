"""
EcoGrid Energy - Main Demonstration Orchestrator

Executes an end-to-end simulation of the peer-to-peer renewable energy trading platform:
1. Initializes configuration, structured logging, and SQLite persistence.
2. Boots decoupled bounded contexts (Smart Meter, Marketplace, Settlement).
3. Connects contexts via the asynchronous EventBus.
4. Generates simulated buyer demand and high-frequency IoT smart meter readings.
5. Executes price-compatible FIFO trade matching and financial settlement.
6. Displays a comprehensive architectural metrics summary.
"""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import List

from shared.config import get_config
from shared.event_bus import EventBus
from shared.logging_config import setup_logging, log_event
from shared.models import EnergyDemandEvent
from smart_meter.simulator import SmartMeterSimulator
from marketplace.service import MarketplaceService
from settlement.service import SettlementService


async def seed_buyer_demands(event_bus: EventBus, count: int = 10, default_max_price: float = 0.30) -> List[EnergyDemandEvent]:
    """
    Seed realistic buyer demand bids into the marketplace.
    """
    buyer_events: List[EnergyDemandEvent] = []
    # Realistic residential & small commercial buyer profiles
    buyer_profiles = [
        ("BYR-001", 15.0, 0.28),
        ("BYR-002", 25.0, 0.30),
        ("BYR-003", 10.5, 0.26),
        ("BYR-004", 40.0, 0.32),
        ("BYR-005", 18.0, 0.29),
        ("BYR-006", 30.0, 0.35),
        ("BYR-007", 12.0, 0.27),
        ("BYR-008", 22.5, 0.30),
        ("BYR-009", 35.0, 0.31),
        ("BYR-010", 50.0, 0.33),
    ]

    for buyer_id, required_kwh, max_price in buyer_profiles[:count]:
        demand = EnergyDemandEvent(
            buyer_id=buyer_id,
            required_kwh=required_kwh,
            maximum_price_per_kwh=max_price,
            timestamp=datetime.now(timezone.utc),
        )
        buyer_events.append(demand)
        await event_bus.publish(demand)

    return buyer_events


async def run_ecogrid_system() -> None:
    """Run the complete end-to-end EcoGrid system demonstration."""
    start_time = time.perf_counter()
    config = get_config()
    logger = setup_logging(config.log_level)

    print("=" * 78)
    print(" ECOGRID ENERGY: P2P RENEWABLE TRADING PLATFORM (ICT711 ASSESSMENT 2)")
    print(" Architecture: Event-Driven Bounded Contexts (Smart Meter -> Market -> Ledger)")
    print("=" * 78)

    # 1. Initialize Event Bus
    event_bus = EventBus(
        max_retries=config.max_retries,
        retry_delay=config.event_retry_delay,
        logger=logger,
    )

    # 2. Initialize Marketplace Context
    marketplace = MarketplaceService(
        event_bus=event_bus,
        default_price_per_kwh=config.default_energy_price,
        logger=logger,
    )
    marketplace.register_subscriptions()

    # 3. Initialize Financial Settlement Context
    settlement = SettlementService(
        event_bus=event_bus,
        database_path=config.database_path,
        logger=logger,
    )
    settlement.register_subscriptions()

    log_event(logger, logging.INFO, "SYSTEM", "Event Bus & Bounded Contexts initialized.")

    # 4. Seed Buyer Energy Demand
    log_event(logger, logging.INFO, "DEMAND", "Publishing buyer demand bids...")
    buyer_events = await seed_buyer_demands(event_bus, count=10, default_max_price=config.default_buyer_max_price)

    # 5. Initialize & Execute Smart Meter Simulation
    simulator = SmartMeterSimulator(
        event_bus=event_bus,
        meter_count=config.simulation_meters,
        readings_per_meter=config.simulation_readings_per_meter,
        delay_seconds=config.simulation_delay,
        random_seed=42,  # Deterministic seed for reproducible evaluation
        logger=logger,
    )

    log_event(logger, logging.INFO, "SMART_METER", "Commencing IoT smart meter data ingestion stream...")
    meter_readings = await simulator.run_simulation()

    # 6. Gather and verify persistence
    persisted_settlements = settlement.get_all_settlements()
    total_db_amount = settlement.get_total_settled_amount()

    elapsed_time = time.perf_counter() - start_time

    # 7. Print Architectural Summary Dashboard
    print("\n" + "=" * 78)
    print(" ECOGRID ENERGY DEMONSTRATION SUMMARY & METRICS DASHBOARD")
    print("=" * 78)
    print(f" Execution Status                : COMPLETED (Auto-terminated)")
    print(f" Total Execution Time            : {elapsed_time:.3f} seconds")
    print(f" High-Frequency Event Ingestion  : {simulator.total_readings_emitted / max(elapsed_time, 0.001):.1f} readings/sec")
    print("-" * 78)
    print(" [1] SMART METER CONTEXT (IoT Ingestion)")
    print(f"     * Simulated Households      : {config.simulation_meters}")
    print(f"     * Total Meter Readings      : {simulator.total_readings_emitted}")
    print(f"     * Solar Generation Recorded : {simulator.total_generation_kwh:.2f} kWh")
    print(f"     * Household Consumption     : {simulator.total_consumption_kwh:.2f} kWh")
    print(f"     * Net Surplus Solar Energy  : {simulator.total_surplus_kwh:.2f} kWh")
    print("-" * 78)
    print(" [2] MARKETPLACE CONTEXT (P2P Matching Engine)")
    print(f"     * Buyer Demand Bids Queued  : {len(buyer_events)} bids ({sum(b.required_kwh for b in buyer_events):.2f} kWh total demand)")
    print(f"     * Total P2P Trades Matched  : {marketplace.total_trades_count}")
    print(f"     * Energy Traded via P2P     : {marketplace.total_energy_traded_kwh:.2f} kWh")
    print(f"     * Unallocated Surplus Supply: {marketplace.pending_supply_kwh:.2f} kWh")
    print(f"     * Remaining Buyer Demand    : {marketplace.pending_demand_kwh:.2f} kWh")
    print("-" * 78)
    print(" [3] FINANCIAL SETTLEMENT CONTEXT (SQLite Ledger)")
    print(f"     * Settlements Completed     : {len(persisted_settlements)}")
    print(f"     * Total Amount Settled      : AUD ${total_db_amount:.2f}")
    print(f"     * Duplicate Trades Blocked  : {settlement.duplicate_trades_ignored}")
    print(f"     * Ledger Database Location  : {Path(config.database_path).resolve()}")
    print("-" * 78)
    print(" [4] EVENT BUS & RESILIENCE METRICS")
    print(f"     * Total Events Published    : {event_bus.total_published}")
    print(f"     * Total Handler Invocations : {event_bus.total_processed}")
    print(f"     * Handler Retries Executed  : {event_bus.total_retries}")
    print(f"     * Dead Letter Queue (DLQ)   : {event_bus.dlq.count()} failed items")
    print("=" * 78)
    print(" All bounded contexts successfully decoupled via Event-Driven Architecture.")
    print("=" * 78 + "\n")


def main() -> None:
    """Entry point for running the EcoGrid Energy demonstration."""
    asyncio.run(run_ecogrid_system())


if __name__ == "__main__":
    main()
