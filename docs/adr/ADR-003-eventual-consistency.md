# ADR-003: Eventual Consistency and Distributed Transaction Strategy

## Status
**Accepted**

## Context
High-throughput distributed systems cannot reliably employ distributed Two-Phase Commit (2PC) or global ACID transactions across IoT ingestion, matching engines, and financial databases without suffering from severe latency penalties, high lock contention, and vulnerability to network partitions (as described by the CAP theorem).

In EcoGrid Energy, physical solar generation occurs continuously in real time, while market clearing and financial ledger writes occur asynchronously downstream.

## Decision
We adopted an **Eventual Consistency** model across bounded contexts:
1. **Asynchronous Progression:** A smart meter reading progresses through the system asynchronously:
   `Smart Meter Reading` $\rightarrow$ `Marketplace Order Book Update` $\rightarrow$ `Trade Matched` $\rightarrow$ `Settlement Persisted`.
2. **Idempotent Consumers:** To guarantee correctness under at-least-once message delivery, the Settlement context enforces strict idempotency using unique `trade_id` keys and database unique constraints.
3. **Compensating Actions Architecture (Saga Pattern Readiness):** In production scenarios where a transaction fails downstream (e.g., buyer payment method declined), the architecture is designed to emit compensating events (`TradeReversalEvent` or `CreditAdjustmentEvent`) rather than holding distributed database locks.

## Consequences

### Positive (Benefits)
- **High Availability & Low Latency:** Publishers complete immediately without waiting for disk I/O in downstream ledgers.
- **Robustness Against Network Partitions:** Each context maintains its local transactional integrity without distributed deadlocks.
- **Replayability:** Events can be replayed from the broker log to reconstruct state or recover from transient downstream outages.

### Negative (Trade-offs)
- **Temporary State Discrepancy:** For brief millisecond intervals, energy may be matched before the financial record is committed to disk.
- **Complexity in Failure Handling:** Requires explicit retry policies, Dead Letter Queues (DLQ), and automated reconciliation audits to detect and resolve stranded events.
