"""
EcoGrid Energy - Asynchronous Event Bus & Dead Letter Queue

Provides a decoupled, asynchronous, in-memory event bus supporting retry policies,
safe exception isolation, and dead letter queue (DLQ) tracking for transient/permanent failures.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from shared.logging_config import log_event


EventHandler = Callable[[Any], Any]


@dataclass(frozen=True)
class DeadLetterItem:
    """
    Represents an event that failed processing across all retry attempts.
    """
    event: Any
    handler_name: str
    error_message: str
    attempts: int
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = "N/A"


class DeadLetterQueue:
    """
    In-memory Dead Letter Queue storing failed events for inspection and audit.
    """

    def __init__(self) -> None:
        self._items: List[DeadLetterItem] = []

    def add(self, item: DeadLetterItem) -> None:
        """Add a failed event item to the DLQ."""
        self._items.append(item)

    def get_all(self) -> List[DeadLetterItem]:
        """Return a copy of all failed event records."""
        return list(self._items)

    def count(self) -> int:
        """Return the number of failed events in the DLQ."""
        return len(self._items)

    def clear(self) -> None:
        """Clear all DLQ items."""
        self._items.clear()


class EventBus:
    """
    Asynchronous in-memory Event Bus enabling decoupled communication
    between bounded contexts (Smart Meter, Marketplace, Settlement).
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 0.01,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._subscribers: Dict[type, List[EventHandler]] = defaultdict(list)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._logger = logger or logging.getLogger("ecogrid")
        self.dlq = DeadLetterQueue()
        self._published_count = 0
        self._processed_count = 0
        self._retry_count = 0

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """
        Register a subscriber handler for a specific domain event type.
        """
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def subscriber_count(self, event_type: type) -> int:
        """
        Return the count of active subscribers for the given event type.
        """
        return len(self._subscribers.get(event_type, []))

    async def publish(self, event: Any) -> int:
        """
        Publish an event to all registered subscribers.
        Executes handlers safely with retry logic and error isolation.
        Returns the number of handlers invoked.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        correlation_id = getattr(event, "correlation_id", "N/A")

        self._published_count += 1
        log_event(
            self._logger,
            logging.DEBUG,
            "EVENT_PUBLISHED",
            f"Event {event_type.__name__} published to {len(handlers)} subscriber(s)",
            correlation_id=correlation_id,
        )

        for handler in handlers:
            await self._invoke_handler_with_retry(handler, event, correlation_id)

        return len(handlers)

    async def _invoke_handler_with_retry(
        self, handler: EventHandler, event: Any, correlation_id: str
    ) -> None:
        """
        Invoke an individual handler with retry logic and DLQ fallback.
        """
        handler_name = getattr(handler, "__qualname__", getattr(handler, "__name__", str(handler)))
        attempt = 0

        while attempt < self._max_retries:
            attempt += 1
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
                self._processed_count += 1
                return
            except Exception as exc:
                self._retry_count += 1
                if attempt < self._max_retries:
                    log_event(
                        self._logger,
                        logging.WARNING,
                        "RETRY",
                        f"Handler '{handler_name}' failed on attempt {attempt}/{self._max_retries}: {exc}. Retrying...",
                        correlation_id=correlation_id,
                    )
                    if self._retry_delay > 0:
                        await asyncio.sleep(self._retry_delay)
                else:
                    # Retries exhausted - record into DLQ
                    log_event(
                        self._logger,
                        logging.ERROR,
                        "DEAD_LETTER",
                        f"Handler '{handler_name}' failed after {attempt} attempts: {exc}. Moved to DLQ.",
                        correlation_id=correlation_id,
                    )
                    dlq_item = DeadLetterItem(
                        event=event,
                        handler_name=handler_name,
                        error_message=str(exc),
                        attempts=attempt,
                        correlation_id=correlation_id,
                    )
                    self.dlq.add(dlq_item)

    @property
    def total_published(self) -> int:
        return self._published_count

    @property
    def total_processed(self) -> int:
        return self._processed_count

    @property
    def total_retries(self) -> int:
        return self._retry_count