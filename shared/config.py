"""
EcoGrid Energy - Application Configuration

Provides strongly typed configuration settings loaded from environment
variables with sensible development defaults.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    database_path: str = os.getenv("DATABASE_PATH", "data/ecogrid.db")
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    event_retry_delay: float = float(os.getenv("EVENT_RETRY_DELAY", "0.01"))
    default_energy_price: float = float(os.getenv("DEFAULT_ENERGY_PRICE", "0.25"))
    default_buyer_max_price: float = float(os.getenv("DEFAULT_BUYER_MAX_PRICE", "0.30"))
    simulation_meters: int = int(os.getenv("SIMULATION_METERS", "20"))
    simulation_readings_per_meter: int = int(os.getenv("SIMULATION_READINGS_PER_METER", "50"))
    simulation_delay: float = float(os.getenv("SIMULATION_DELAY", "0.0"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


def get_config() -> AppConfig:
    """Retrieve an instance of AppConfig."""
    return AppConfig()
