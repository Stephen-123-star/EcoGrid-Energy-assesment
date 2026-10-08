"""
EcoGrid Energy - Shared Domain Event Models

This module defines the immutable domain event contracts used across the
EcoGrid bounded contexts (Smart Meter Integration, Marketplace, Settlement).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class MeterReadingEvent:
    """
    Event emitted when a smart meter records solar generation and household consumption.
    """
    meter_id: str
    household_id: str
    generation_kwh: float
    consumption_kwh: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.meter_id or not isinstance(self.meter_id, str):
            raise ValueError("meter_id must be a non-empty string.")
        if not self.household_id or not isinstance(self.household_id, str):
            raise ValueError("household_id must be a non-empty string.")
        if self.generation_kwh < 0:
            raise ValueError(f"generation_kwh cannot be negative, got {self.generation_kwh}.")
        if self.consumption_kwh < 0:
            raise ValueError(f"consumption_kwh cannot be negative, got {self.consumption_kwh}.")

    @property
    def surplus_kwh(self) -> float:
        """
        Calculate surplus electricity available for peer-to-peer sale.
        """
        surplus = self.generation_kwh - self.consumption_kwh
        return round(max(surplus, 0.0), 3)


@dataclass(frozen=True)
class EnergyDemandEvent:
    """
    Event emitted when a consumer requests renewable electricity from the marketplace.
    """
    buyer_id: str
    required_kwh: float
    maximum_price_per_kwh: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.buyer_id or not isinstance(self.buyer_id, str):
            raise ValueError("buyer_id must be a non-empty string.")
        if self.required_kwh <= 0:
            raise ValueError(f"required_kwh must be positive, got {self.required_kwh}.")
        if self.maximum_price_per_kwh <= 0:
            raise ValueError(f"maximum_price_per_kwh must be positive, got {self.maximum_price_per_kwh}.")


@dataclass(frozen=True)
class TradeMatchedEvent:
    """
    Event emitted when the Marketplace matches an energy seller with a buyer.
    """
    trade_id: str
    seller_id: str
    buyer_id: str
    energy_kwh: float
    price_per_kwh: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.trade_id or not isinstance(self.trade_id, str):
            raise ValueError("trade_id must be a non-empty string.")
        if not self.seller_id or not isinstance(self.seller_id, str):
            raise ValueError("seller_id must be a non-empty string.")
        if not self.buyer_id or not isinstance(self.buyer_id, str):
            raise ValueError("buyer_id must be a non-empty string.")
        if self.energy_kwh <= 0:
            raise ValueError(f"energy_kwh must be positive, got {self.energy_kwh}.")
        if self.price_per_kwh <= 0:
            raise ValueError(f"price_per_kwh must be positive, got {self.price_per_kwh}.")

    @property
    def total_amount(self) -> float:
        """
        Calculate total monetary value of the matched trade in AUD.
        """
        return round(self.energy_kwh * self.price_per_kwh, 2)


@dataclass(frozen=True)
class SettlementCompletedEvent:
    """
    Event emitted when the Financial Settlement context completes and persists a trade transaction.
    """
    settlement_id: str
    trade_id: str
    seller_id: str
    buyer_id: str
    energy_kwh: float
    price_per_kwh: float
    total_amount: float
    status: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.settlement_id or not isinstance(self.settlement_id, str):
            raise ValueError("settlement_id must be a non-empty string.")
        if not self.trade_id or not isinstance(self.trade_id, str):
            raise ValueError("trade_id must be a non-empty string.")
        if self.total_amount < 0:
            raise ValueError(f"total_amount cannot be negative, got {self.total_amount}.")