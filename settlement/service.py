"""
EcoGrid Energy - Financial Settlement Bounded Context: Service

Handles secure micro-transactions for matched electricity trades. Subscribes to
TradeMatchedEvent, enforces strict idempotency via SQLite constraints, executes
parameterized persistence, and publishes SettlementCompletedEvent.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from shared.event_bus import EventBus
from shared.logging_config import log_event
from shared.models import SettlementCompletedEvent, TradeMatchedEvent


class SettlementService:
    """
    Financial Settlement bounded context service managing persistent ledger
    entries for energy trades with strict transaction safety and idempotency.
    """

    def __init__(
        self,
        event_bus: EventBus,
        database_path: str = "data/ecogrid.db",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._event_bus = event_bus
        self._db_path = database_path
        self._logger = logger or logging.getLogger("ecogrid")

        # Operational metrics
        self.total_settlements_count = 0
        self.total_settled_amount_aud = 0.0
        self.duplicate_trades_ignored = 0

        self._init_connection()
        self._ensure_database_ready()

    def _init_connection(self) -> None:
        """Initialize reusable SQLite connection."""
        if self._db_path != ":memory:":
            db_dir = Path(self._db_path).parent
            if db_dir and not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")

    def _get_connection(self) -> sqlite3.Connection:
        """Return the active SQLite connection."""
        return self._conn

    def _ensure_database_ready(self) -> None:
        """Initialize SQLite schema if not already present."""
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS settlements (
                    settlement_id TEXT PRIMARY KEY,
                    trade_id TEXT UNIQUE NOT NULL,
                    seller_id TEXT NOT NULL,
                    buyer_id TEXT NOT NULL,
                    energy_kwh REAL NOT NULL,
                    price_per_kwh REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    correlation_id TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_settlements_trade_id
                ON settlements(trade_id)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_settlements_seller_id
                ON settlements(seller_id)
            """)

    def register_subscriptions(self) -> None:
        """Subscribe to TradeMatchedEvent on the event bus."""
        self._event_bus.subscribe(TradeMatchedEvent, self.handle_trade_matched)

    async def handle_trade_matched(self, event: TradeMatchedEvent) -> Optional[SettlementCompletedEvent]:
        """
        Process a matched trade event, verify idempotency, persist the settlement,
        and publish SettlementCompletedEvent.
        """
        # 1. Validation check
        if event.energy_kwh <= 0 or event.price_per_kwh <= 0:
            raise ValueError(f"Invalid trade quantities: energy={event.energy_kwh}, price={event.price_per_kwh}")

        # 2. Check Idempotency before persisting
        if self.is_trade_settled(event.trade_id):
            self.duplicate_trades_ignored += 1
            log_event(
                self._logger,
                logging.WARNING,
                "SETTLEMENT_COMPLETED",
                f"Duplicate trade received [{event.trade_id}]. Idempotency check skipped duplicate persistence.",
                correlation_id=event.correlation_id,
            )
            return None

        settlement_id = f"SET-{uuid.uuid4().hex[:8].upper()}"
        total_amount = event.total_amount
        created_at_iso = datetime.now(timezone.utc).isoformat()
        status = "SETTLED"

        # 3. Persist record using parameterized query within atomic transaction
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO settlements (
                        settlement_id, trade_id, seller_id, buyer_id,
                        energy_kwh, price_per_kwh, total_amount, status,
                        created_at, correlation_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        settlement_id,
                        event.trade_id,
                        event.seller_id,
                        event.buyer_id,
                        event.energy_kwh,
                        event.price_per_kwh,
                        total_amount,
                        status,
                        created_at_iso,
                        event.correlation_id,
                    ),
                )
            self.total_settlements_count += 1
            self.total_settled_amount_aud = round(self.total_settled_amount_aud + total_amount, 2)

            log_event(
                self._logger,
                logging.INFO,
                "SETTLEMENT_COMPLETED",
                f"Settled Trade [{event.trade_id}] as Settlement [{settlement_id}]: AUD {total_amount:.2f} ({event.energy_kwh} kWh @ AUD {event.price_per_kwh:.2f}) -> {event.seller_id} from {event.buyer_id}",
                correlation_id=event.correlation_id,
            )

            # 4. Emit SettlementCompletedEvent
            settled_event = SettlementCompletedEvent(
                settlement_id=settlement_id,
                trade_id=event.trade_id,
                seller_id=event.seller_id,
                buyer_id=event.buyer_id,
                energy_kwh=event.energy_kwh,
                price_per_kwh=event.price_per_kwh,
                total_amount=total_amount,
                status=status,
                timestamp=datetime.now(timezone.utc),
                correlation_id=event.correlation_id,
            )
            await self._event_bus.publish(settled_event)
            return settled_event

        except sqlite3.IntegrityError as exc:
            # Handles race condition where trade_id was inserted concurrently
            self.duplicate_trades_ignored += 1
            log_event(
                self._logger,
                logging.WARNING,
                "SETTLEMENT_COMPLETED",
                f"Integrity constraint prevented duplicate trade settlement for {event.trade_id}: {exc}",
                correlation_id=event.correlation_id,
            )
            return None

    def is_trade_settled(self, trade_id: str) -> bool:
        """Check if a settlement record already exists for the given trade_id."""
        cursor = self._conn.execute(
            "SELECT 1 FROM settlements WHERE trade_id = ?",
            (trade_id,),
        )
        return cursor.fetchone() is not None

    def get_settlement_by_trade_id(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a settlement record by trade_id."""
        cursor = self._conn.execute(
            "SELECT * FROM settlements WHERE trade_id = ?",
            (trade_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_settlements(self) -> List[Dict[str, Any]]:
        """Retrieve all settled records from the SQLite ledger."""
        cursor = self._conn.execute("SELECT * FROM settlements ORDER BY created_at ASC")
        return [dict(row) for row in cursor.fetchall()]

    def get_settlement_count(self) -> int:
        """Return the count of persisted settlements in the database."""
        cursor = self._conn.execute("SELECT COUNT(*) AS count FROM settlements")
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_total_settled_amount(self) -> float:
        """Return the sum total of all settled monetary amounts in AUD."""
        cursor = self._conn.execute("SELECT COALESCE(SUM(total_amount), 0.0) AS total FROM settlements")
        row = cursor.fetchone()
        return round(row["total"], 2) if row else 0.0

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    def __del__(self) -> None:
        self.close()
