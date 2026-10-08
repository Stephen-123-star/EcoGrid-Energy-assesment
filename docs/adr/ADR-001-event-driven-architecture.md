# ADR-001: Event-Driven Architecture for High-Frequency Smart Meter Ingestion

## Status
**Accepted**

## Context
EcoGrid Energy is a peer-to-peer (P2P) renewable energy platform where residential homeowners with rooftop solar photovoltaic (PV) systems trade surplus electricity with local consumers. The system must ingest high-frequency generation and consumption telemetry from thousands of IoT smart meters while matching buyers and sellers and recording financial settlements.

A traditional synchronous, request-response architecture (e.g., RESTful HTTP endpoints between internal services) introduces critical architectural risks:
1. **Tight Temporal Coupling:** The smart meter ingestion pipeline would block waiting for the marketplace matching engine and financial database writes to complete.
2. **Cascading Failures:** A transient latency spike or outage in the financial settlement ledger would cause backpressure and crash high-frequency IoT ingestion.
3. **Throughput Bottlenecks:** Synchronous locking around order books and database transactions limits horizontal scalability.

## Decision
We adopted an **Asynchronous Event-Driven Architecture (EDA)** utilizing Domain Events (`MeterReadingEvent`, `EnergyDemandEvent`, `TradeMatchedEvent`, `SettlementCompletedEvent`) dispatched over an asynchronous event bus (`EventBus`).

In this proof-of-concept (PoC), an in-memory asynchronous event bus with retry logic and a Dead Letter Queue (DLQ) is implemented, serving as an architectural blueprint for a production distributed message broker (such as Apache Kafka, RabbitMQ, or AWS EventBridge/SNS/SQS).

## Consequences

### Positive (Benefits)
- **High Ingestion Throughput:** Smart meter ingestion publishes events non-blockingly without waiting for matching or ledger persistence.
- **Fault Isolation:** A failure in settlement processing or downstream reporting does not disrupt smart meter telemetry ingestion or marketplace matching.
- **Temporal & Spatial Decoupling:** Publishers and subscribers do not have compile-time or runtime knowledge of each other's existence.
- **Extensibility / Evolvability:** New downstream consumers (such as carbon credit auditors or grid frequency monitors) can subscribe to events without modifying existing publishers.

### Negative (Trade-offs & "Complexity Tax")
- **Eventual Consistency:** System state is eventually consistent rather than immediately consistent across all bounded contexts.
- **Debugging Complexity:** Tracing transaction lifecycles requires distributed tracing and correlation IDs (`correlation_id`).
- **Operational Overhead:** A production deployment requires managing and monitoring distributed broker infrastructure (e.g., partition rebalancing, consumer lag, schema registries).
