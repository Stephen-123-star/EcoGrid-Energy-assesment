"""
EcoGrid Energy - Marketplace Bounded Context: Service

Handles peer-to-peer renewable energy matching. Subscribes to MeterReadingEvent
(surplus supply) and EnergyDemandEvent (buyer requests), executing price-compatible
FIFO matching and publishing TradeMatchedEvent without coupling to settlement persistence.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Deque, List, Optional
import uuid

from shared.event_bus import EventBus
from shared.logging_config import log_event
from shared.models import EnergyDemandEvent, MeterReadingEvent, TradeMatchedEvent


@dataclass
class SupplyOffer:
    """Internal marketplace representation of an available energy offer."""
    seller_id: str
    available_kwh: float
    timestamp: datetime
    correlation_id: str


@dataclass
class DemandBid:
    """Internal marketplace representation of an active buyer bid."""
    buyer_id: str
    remaining_kwh: float
    maximum_price_per_kwh: float
    timestamp: datetime
    correlation_id: str


class MarketplaceService:
    """
    Marketplace bounded context service responsible for matching seller surplus
    with buyer demand while preventing overselling and isolating trading rules.
    """

    def __init__(
        self,
        event_bus: EventBus,
        default_price_per_kwh: float = 0.25,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._event_bus = event_bus
        self._default_price = default_price_per_kwh
        self._logger = logger or logging.getLogger("ecogrid")

        # In-memory order books (FIFO queues)
        self._supply_queue: Deque[SupplyOffer] = deque()
        self._demand_queue: Deque[DemandBid] = deque()

        # Operational metrics
        self.total_surplus_received_kwh = 0.0
        self.total_demand_received_kwh = 0.0
        self.total_energy_traded_kwh = 0.0
        self.total_trades_count = 0
        self.matched_trades: List[TradeMatchedEvent] = []

    def register_subscriptions(self) -> None:
        """Subscribe to incoming domain events from the event bus."""
        self._event_bus.subscribe(MeterReadingEvent, self.handle_meter_reading)
        self._event_bus.subscribe(EnergyDemandEvent, self.handle_energy_demand)

    async def handle_meter_reading(self, event: MeterReadingEvent) -> None:
        """
        Process meter reading event. If household has surplus solar,
        enqueue supply offer and evaluate matching engine.
        """
        if event.surplus_kwh > 0:
            self.total_surplus_received_kwh = round(
                self.total_surplus_received_kwh + event.surplus_kwh, 3
            )
            offer = SupplyOffer(
                seller_id=event.household_id,
                available_kwh=event.surplus_kwh,
                timestamp=event.timestamp,
                correlation_id=event.correlation_id,
            )
            self._supply_queue.append(offer)
            log_event(
                self._logger,
                logging.DEBUG,
                "SURPLUS_AVAILABLE",
                f"Queued {offer.available_kwh} kWh supply offer from seller {offer.seller_id}",
                correlation_id=event.correlation_id,
            )
            await self._match_orders()

    async def handle_energy_demand(self, event: EnergyDemandEvent) -> None:
        """
        Process energy demand event from a prospective buyer.
        Enqueue demand bid and evaluate matching engine.
        """
        self.total_demand_received_kwh = round(
            self.total_demand_received_kwh + event.required_kwh, 3
        )
        bid = DemandBid(
            buyer_id=event.buyer_id,
            remaining_kwh=event.required_kwh,
            maximum_price_per_kwh=event.maximum_price_per_kwh,
            timestamp=event.timestamp,
            correlation_id=event.correlation_id,
        )
        self._demand_queue.append(bid)
        log_event(
            self._logger,
            logging.INFO,
            "DEMAND_RECEIVED",
            f"Queued demand for {bid.remaining_kwh} kWh by buyer {bid.buyer_id} (max {bid.maximum_price_per_kwh:.2f} AUD/kWh)",
            correlation_id=event.correlation_id,
        )
        await self._match_orders()

    async def _match_orders(self) -> None:
        """
        Execute Price-Compatible FIFO matching algorithm.
        Matches available seller supply against active buyer demand,
        strictly preventing overselling and publishing TradeMatchedEvent.
        """
        while self._supply_queue and self._demand_queue:
            current_supply = self._supply_queue[0]
            current_demand = self._demand_queue[0]

            # Price compatibility check
            clearing_price = self._default_price
            if clearing_price > current_demand.maximum_price_per_kwh:
                # Incompatible price - skip or retain bid
                log_event(
                    self._logger,
                    logging.WARNING,
                    "MARKETPLACE",
                    f"Demand price limit {current_demand.maximum_price_per_kwh:.2f} below market price {clearing_price:.2f}",
                    correlation_id=current_demand.correlation_id,
                )
                break

            # Avoid self-trading (same household cannot sell to itself)
            if current_supply.seller_id == current_demand.buyer_id:
                # If seller and buyer are the same entity, pop supply to avoid deadlock
                self._supply_queue.popleft()
                continue

            # Determine trade quantity
            trade_kwh = round(min(current_supply.available_kwh, current_demand.remaining_kwh), 3)

            if trade_kwh <= 0:
                break

            trade_id = f"TRD-{uuid.uuid4().hex[:8].upper()}"
            trade_event = TradeMatchedEvent(
                trade_id=trade_id,
                seller_id=current_supply.seller_id,
                buyer_id=current_demand.buyer_id,
                energy_kwh=trade_kwh,
                price_per_kwh=clearing_price,
                timestamp=datetime.now(timezone.utc),
                correlation_id=current_demand.correlation_id,
            )

            # Update queues
            current_supply.available_kwh = round(current_supply.available_kwh - trade_kwh, 3)
            current_demand.remaining_kwh = round(current_demand.remaining_kwh - trade_kwh, 3)

            if current_supply.available_kwh <= 0:
                self._supply_queue.popleft()

            if current_demand.remaining_kwh <= 0:
                self._demand_queue.popleft()

            # Record metrics
            self.total_trades_count += 1
            self.total_energy_traded_kwh = round(self.total_energy_traded_kwh + trade_kwh, 3)
            self.matched_trades.append(trade_event)

            log_event(
                self._logger,
                logging.INFO,
                "TRADE_MATCHED",
                f"Matched Trade [{trade_id}]: {trade_kwh} kWh from {trade_event.seller_id} to {trade_event.buyer_id} @ AUD {clearing_price:.2f}/kWh (Total: AUD {trade_event.total_amount:.2f})",
                correlation_id=trade_event.correlation_id,
            )

            # Publish trade event to decoupled event bus
            await self._event_bus.publish(trade_event)

    @property
    def pending_supply_kwh(self) -> float:
        """Return total unallocated supply in the queue."""
        return round(sum(s.available_kwh for s in self._supply_queue), 3)

    @property
    def pending_demand_kwh(self) -> float:
        """Return total unfulfilled demand in the queue."""
        return round(sum(d.remaining_kwh for d in self._demand_queue), 3)
