# EcoGrid Energy - Resilience & Fault-Tolerance Architecture

## 1. Resilience Philosophy

In an asynchronous IoT energy trading platform, failures are inevitable: smart meter telemetry may suffer network drops, marketplace order queues may face burst load, and financial databases may experience temporary connection saturation.

EcoGrid Energy implements a defense-in-depth resilience model ensuring that no single component failure can crash the entire platform or corrupt financial records.

---

## 2. Core Resilience Mechanisms

### A. Transient Retry Policy with Backoff
When an event handler encounters a transient exception (such as a temporary network timeout or database lock contention):
- The `EventBus` intercepts the error and increments an attempt counter.
- It logs a structured `[RETRY]` warning with the handler name, attempt number, and `correlation_id`.
- It executes a non-blocking backoff delay (`asyncio.sleep(retry_delay)`).
- Up to `max_retries` (default: 3 attempts) are made before declaring failure.

### B. Dead Letter Queue (DLQ) Containment
If a handler fails repeatedly and exhausts all retry attempts:
- The event is **not dropped silently**.
- It is encapsulated into a `DeadLetterItem` containing the original event, handler name, error message, retry count, timestamp, and `correlation_id`.
- The item is deposited into the `DeadLetterQueue` (DLQ) for operator inspection, alerting, or manual replay.
- An `[ERROR]` log entry is emitted with domain event tags.

### C. Financial Settlement Idempotency
In distributed systems, networks guarantee *at-least-once* delivery. As a result, duplicate `TradeMatchedEvent` messages may arrive due to network retries or client retransmissions.
- The `SettlementService` performs an explicit idempotency check (`is_trade_settled(trade_id)`) before initiating an insert.
- The SQLite ledger enforces a database-level `UNIQUE` constraint on the `trade_id` column.
- If a duplicate event arrives, the system emits a `[WARNING]` log and drops the duplicate without double-billing or corrupting ledger sums.

### D. Subscriber Fault Isolation & Blast Radius Containment
- Each subscriber handler is wrapped in an isolated `try...except` execution block within the `EventBus`.
- If Subscriber A crashes or raises an unhandled exception, Subscriber B continues processing unaffected.
- The event publisher is completely isolated and never receives an unhandled exception from downstream subscribers.

### E. Distributed Tracing via Correlation IDs
- Every domain event automatically generates a UUIDv4 `correlation_id` upon instantiation (or propagates the caller's ID).
- Structured logging tags every log entry with `[CID: <id>]`, allowing an engineer to trace a single smart meter reading across the entire lifecycle:
  `METER_READING` $\rightarrow$ `SURPLUS_AVAILABLE` $\rightarrow$ `TRADE_MATCHED` $\rightarrow$ `SETTLEMENT_COMPLETED`.

---

## 3. Failure-Mode & Effects Analysis (FMEA) Matrix

The table below catalogs key potential failure scenarios, their architectural impacts, detection mechanisms, and implemented mitigations:

| Failure Scenario | Effect on System | Detection Mechanism | Implemented Mitigation |
| :--- | :--- | :--- | :--- |
| **IoT Smart Meter Telemetry Burst** | Sudden influx of generation readings exceeds processing capacity. | EventBus queue latency & processing duration metrics. | Non-blocking asynchronous ingestion; readings are processed in order without blocking IoT emitters. |
| **Transient Database Lock Contention** | Settlement insert temporarily fails due to SQLite disk lock. | Exception caught by `EventBus` during handler execution. | Automatic retry mechanism with configurable delay (3 attempts before DLQ). |
| **Corrupted or Malformed Event Payload** | Invalid negative energy or price values submitted. | Dataclass `__post_init__` validation raises `ValueError`. | Model rejection at the boundary; invalid event is prevented from entering the event bus. |
| **Network Replay / Duplicate Trade Event** | Duplicate `TradeMatchedEvent` dispatched over the bus. | Idempotency query and SQLite `UNIQUE(trade_id)` index. | Settlement service detects existing trade, logs warning, and skips duplicate ledger write. |
| **Persistent Downstream Service Crash** | Downstream notification or ledger service permanently unavailable. | Retries exhausted counter reaches `max_retries`. | Event safely routed to `DeadLetterQueue` (DLQ); system logs `[DEAD_LETTER]` error without crashing publishers. |
| **Database Corruption or Disk Full** | Database writes fail permanently. | SQLite `OperationalError` / `DatabaseError` caught. | Isolated in Settlement service; DLQ captures trade events for replay once storage is restored. |
