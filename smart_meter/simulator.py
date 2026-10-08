"""
EcoGrid Energy - Smart Meter Bounded Context: Simulator

Simulates high-frequency IoT smart meter readings for residential households,
generating and publishing MeterReadingEvent events onto the event bus.
"""

import asyncio
from datetime import datetime, timezone
import logging
import random
from typing import List, Optional

from shared.event_bus import EventBus
from shared.logging_config import log_event
from shared.models import MeterReadingEvent


class SmartMeterSimulator:
    """
    Simulates high-frequency generation and consumption readings from IoT smart meters.
    Keeps smart meter ingestion fully decoupled from marketplace matching.
    """

    def __init__(
        self,
        event_bus: EventBus,
        meter_count: int = 20,
        readings_per_meter: int = 50,
        delay_seconds: float = 0.0,
        random_seed: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._event_bus = event_bus
        self._meter_count = meter_count
        self._readings_per_meter = readings_per_meter
        self._delay_seconds = delay_seconds
        self._logger = logger or logging.getLogger("ecogrid")
        self._rng = random.Random(random_seed)

        # Simulation metrics
        self.total_readings_emitted = 0
        self.total_generation_kwh = 0.0
        self.total_consumption_kwh = 0.0
        self.total_surplus_kwh = 0.0

    def generate_single_reading(self, meter_idx: int) -> MeterReadingEvent:
        """
        Generate a single realistic meter reading event.
        Certain households have high solar capacity, others moderate or low.
        """
        meter_id = f"MTR-{meter_idx + 1:03d}"
        household_id = f"HH-{meter_idx + 1:03d}"

        # Solar solar profile: mix of high producers (60%), medium (30%), low/zero (10%)
        profile = (meter_idx % 10)
        if profile < 6:
            generation = round(self._rng.uniform(1.8, 5.0), 3)
            consumption = round(self._rng.uniform(0.4, 2.0), 3)
        elif profile < 9:
            generation = round(self._rng.uniform(0.5, 2.0), 3)
            consumption = round(self._rng.uniform(0.5, 2.2), 3)
        else:
            generation = round(self._rng.uniform(0.0, 0.5), 3)
            consumption = round(self._rng.uniform(0.8, 2.5), 3)

        event = MeterReadingEvent(
            meter_id=meter_id,
            household_id=household_id,
            generation_kwh=generation,
            consumption_kwh=consumption,
            timestamp=datetime.now(timezone.utc),
        )

        return event

    async def run_simulation(self) -> List[MeterReadingEvent]:
        """
        Run the complete smart meter simulation loop.
        Publishes readings to the event bus in high-frequency batches.
        """
        emitted_events: List[MeterReadingEvent] = []

        log_event(
            self._logger,
            logging.INFO,
            "METER_READING",
            f"Starting smart meter simulation: {self._meter_count} meters x {self._readings_per_meter} readings ({self._meter_count * self._readings_per_meter} total events)",
        )

        for reading_idx in range(self._readings_per_meter):
            for meter_idx in range(self._meter_count):
                event = self.generate_single_reading(meter_idx)
                emitted_events.append(event)

                self.total_readings_emitted += 1
                self.total_generation_kwh = round(self.total_generation_kwh + event.generation_kwh, 3)
                self.total_consumption_kwh = round(self.total_consumption_kwh + event.consumption_kwh, 3)
                self.total_surplus_kwh = round(self.total_surplus_kwh + event.surplus_kwh, 3)

                if event.surplus_kwh > 0:
                    log_event(
                        self._logger,
                        logging.DEBUG,
                        "SURPLUS_AVAILABLE",
                        f"Meter {event.meter_id} generated {event.generation_kwh} kWh, consumed {event.consumption_kwh} kWh -> surplus {event.surplus_kwh} kWh",
                        correlation_id=event.correlation_id,
                    )

                await self._event_bus.publish(event)

                if self._delay_seconds > 0:
                    await asyncio.sleep(self._delay_seconds)

        log_event(
            self._logger,
            logging.INFO,
            "METER_READING",
            f"Smart meter simulation completed: {self.total_readings_emitted} readings emitted, {self.total_surplus_kwh:.2f} kWh total surplus solar.",
        )

        return emitted_events
