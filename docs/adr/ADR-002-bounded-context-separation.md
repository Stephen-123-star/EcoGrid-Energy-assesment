# ADR-002: Domain-Driven Design Bounded Context Separation

## Status
**Accepted**

## Context
In monolithic and poorly modularized software, domain concepts easily become coupled. In the EcoGrid domain:
- **Smart Meter Integration** operates in the realm of IoT hardware telemetry, watt-hours, timestamps, and physical metering identifiers.
- **Marketplace** operates in the realm of economic matching, order books, bids, offers, pricing thresholds, and allocation algorithms.
- **Financial Settlement** operates in the realm of monetary transactions, double-entry ledgers, idempotency keys, and regulatory auditability.

Allowing Marketplace code to directly invoke Settlement database persistence or embedding IoT hardware parsing in the Marketplace violates the Single Responsibility Principle and creates tightly coupled, unmaintainable code.

## Decision
We structured the system into three explicit **Bounded Contexts** following Domain-Driven Design (DDD):
1. `smart_meter`: Responsible exclusively for IoT device ingestion, calculation of local solar surplus, and publishing `MeterReadingEvent`.
2. `marketplace`: Responsible exclusively for maintaining in-memory supply/demand order books, executing FIFO matching, preventing energy overselling, and publishing `TradeMatchedEvent`.
3. `settlement`: Responsible exclusively for processing matched trades, enforcing idempotency, calculating AUD value, and persisting ACID transactions.

A lean `shared` package is restricted exclusively to cross-cutting infrastructure contracts (event dataclasses, logging utilities, configuration, and generic event bus plumbing). Direct cross-context package imports between domain modules are forbidden and strictly enforced by architectural fitness functions.

## Consequences

### Positive (Benefits)
- **High Maintainability:** Each domain context can evolve independently without unintended side effects in adjacent domains.
- **Clear Team Boundaries:** In a growing engineering organization, independent feature teams can own specific bounded contexts without code conflicts.
- **Enforced Security & Validation:** Each bounded context independently validates incoming domain contracts.

### Negative (Trade-offs)
- **Data Duplication / Mapping:** Data from smart meter events is translated into internal marketplace offers and settlement records rather than sharing a single global relational table.
- **Strict Boundary Governance:** Requires automated fitness functions and continuous code review to prevent developers from introducing shortcut cross-domain imports.
