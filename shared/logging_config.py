"""
EcoGrid Energy - Observability & Structured Logging

Configures unified, structured logging across all EcoGrid bounded contexts
with support for correlation IDs, ISO-8601 timestamps, and event tags.
"""

import logging
import sys
from typing import Optional


class EcoGridFormatter(logging.Formatter):
    """
    Custom formatter ensuring consistent timestamp, level, domain context,
    and message formatting across the system.
    """

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", "N/A")
        event_tag = getattr(record, "event_tag", "SYSTEM")
        record.ecogrid_prefix = f"[{event_tag}] [CID: {correlation_id[:8] if correlation_id != 'N/A' else '--------'}]"
        return super().format(record)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Initialize root logging configuration for EcoGrid.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("ecogrid")
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = EcoGridFormatter(
            fmt="%(asctime)s [%(levelname)s] %(ecogrid_prefix)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event_tag: str,
    message: str,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Helper to log structured domain events with correlation tracking.
    """
    extra = {
        "event_tag": event_tag,
        "correlation_id": correlation_id or "N/A",
    }
    logger.log(level, message, extra=extra)
