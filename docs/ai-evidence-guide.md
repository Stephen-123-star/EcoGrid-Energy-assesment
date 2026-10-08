# EcoGrid Energy - AI Interaction & Evidence Guide

## 1. Controlled / Amber AI Compliance Guidelines

In accordance with academic integrity requirements for **ICT711 Assessment 2**, generative AI tools must be used in a transparent, critically evaluated, and documented manner (Controlled / Amber category).

Students are required to document:
1. **Initial Prompt:** The original prompt used to explore the architectural design.
2. **Initial AI Response:** A critical evaluation of what the AI produced versus the assessment requirements.
3. **Three Progressive Refinements:** Successive prompt iterations that guided the AI to correct deficiencies, improve design quality, or add required fitness functions.
4. **Critical Evaluation:** What was accepted, modified, or rejected, along with engineering justifications.

---

## 2. AI Design Tracking Table (Assessment Template)

Fill in this table with the actual prompts and evaluations from your project:

| Stage | Prompt Used | AI Response Summary | Accepted Elements | Modified Elements | Rejected Elements | Engineering Justification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Initial Attempt** | *[Insert initial prompt asking for EcoGrid P2P architecture]* | AI generated a single monolithic script with synchronous method calls between classes. | Domain dataclass definitions and initial solar surplus formula. | Separated the code into 3 distinct bounded contexts (`smart_meter`, `marketplace`, `settlement`). | Rejected direct function calls between Marketplace and Settlement persistence. | Synchronous calls violate decoupling and cause cascading failures under IoT load. |
| **Refinement 1** | *[Insert prompt requesting asynchronous Event-Driven Architecture & EventBus]* | AI created an in-memory EventBus with async publish/subscribe capabilities. | Async event dispatch and type-safe handler registration. | Added retry policies with backoff and Dead Letter Queue (DLQ) support for transient failures. | Rejected complex third-party messaging dependencies (e.g. heavy external brokers) for local PoC. | In-memory async bus provides clean architectural demonstration without unnecessary DevOps overhead. |
| **Refinement 2** | *[Insert prompt requesting Financial Settlement idempotency & SQLite persistence]* | AI implemented basic SQLite database insertion with SQL queries. | Schema creation for `settlements` table and ACID transaction blocks. | Converted all raw queries to parameterized SQL (`?`) and added unique index on `trade_id`. | Rejected in-memory dummy dictionaries for financial transaction storage. | Financial systems require ACID compliance, SQL injection immunity, and strict idempotency. |
| **Refinement 3** | *[Insert prompt requesting Architectural Fitness Functions for FAST, SECURE, MAINTAINABLE, EVOLVABLE, RESILIENT]* | AI generated unit tests covering functional logic and fitness function quality gates. | Automated test suite verifying throughput, secret security, DDD package isolation, and dynamic subscriber extension. | Calibrated performance thresholds for cross-platform stability (>100 events/sec). | Rejected unrealistically tight microsecond benchmarks that fail on slower hardware. | Fitness functions must be robust, deterministic, and repeatable across different student laptops. |

---

## 3. Three Suggested Progressive Refinement Prompts (For Manual Execution)

To continue refining the EcoGrid architecture during your presentation prep or further coursework, you can run these progressive prompts:

### Suggested Prompt 1: Dynamic Pricing & Congestion Management
> *"Refine the Marketplace bounded context to implement a dynamic local tariff algorithm: when local solar surplus in a feeder exceeds 70% of total neighborhood capacity, automatically discount the clearing price by 15% to stimulate local consumption and alleviate grid voltage spikes."*

### Suggested Prompt 2: Saga Compensating Transactions for Settlement Failures
> *"Extend the Financial Settlement service to implement a Saga pattern: if an external bank gateway declines a buyer's payment method after a trade is matched, emit a TradeReversalEvent that notifies the Marketplace to release the reserved energy back to the open order book."*

### Suggested Prompt 3: Grid Frequency & Battery Storage Integration Context
> *"Add a fourth bounded context named 'battery_storage' that subscribes to MeterReadingEvent: when household solar surplus is detected but no buyer demand exists in the marketplace, automatically route the excess energy into a virtual community battery."*
