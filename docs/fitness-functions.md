# EcoGrid Energy - Architectural Fitness Functions

## 1. Architectural Fitness Functions Overview

As defined in evolutionary architecture theory, an **Architectural Fitness Function** provides an objective, automated integrity assessment of an architectural characteristic (such as performance, security, maintainability, evolvability, or resilience).

In EcoGrid Energy, all fitness functions are implemented as executable tests in `tests/test_fitness_functions.py` and run automatically in CI/CD.

---

## 2. Fitness Function Catalog

### 1. Performance Fitness Function (FAST)
- **Quality Attribute:** Performance & High-Frequency Ingestion Throughput
- **Fitness Function:** `test_ff_performance_high_frequency_throughput`
- **Measurement:** Wall-clock duration and events processed per second for a batch of 200 smart meter events through the entire decoupled pipeline (Ingestion $\rightarrow$ Marketplace $\rightarrow$ Settlement $\rightarrow$ SQLite).
- **Threshold / Rule:** Total execution time must be $< 2.0\text{ seconds}$, maintaining a sustained processing throughput of $> 100\text{ events/sec}$ on standard test hardware.
- **Reason:** IoT smart meters emit telemetry continuously. A throughput bottleneck in event dispatching would lead to unbounded memory queues and dropped telemetry.

### 2. Security Fitness Function (SECURE)
- **Quality Attribute:** Input Validation & Data Integrity
- **Fitness Functions:**
  - `test_ff_security_input_validation_and_injection_immunity`
  - `test_ff_security_git_ignores_secrets_and_databases`
- **Measurement:**
  - Attempting to instantiate domain events with negative values, zero pricing, or invalid types.
  - Verifying `.gitignore` explicitly excludes `.env` credentials and `data/*.db` database files.
- **Threshold / Rule:** Any invalid data or malicious input must raise a `ValueError` immediately at the domain perimeter. Secrets and SQLite databases must never be staged into version control.
- **Reason:** Renewable energy trading involves financial transactions. Flawed input validation could lead to negative pricing exploits, overselling of non-existent solar power, or credential leakage in public repositories.

### 3. Maintainability Fitness Function (MAINTAINABLE)
- **Quality Attribute:** Bounded Context Modularity & Low Coupling
- **Fitness Function:** `test_ff_maintainability_bounded_context_independence`
- **Measurement:** Static reflection inspecting the imported modules of `smart_meter` and `marketplace`.
- **Threshold / Rule:** `smart_meter` and `marketplace` modules must have zero imports of `sqlite3` or `SettlementService`.
- **Reason:** Prevents "architectural erosion" where developers accidentally introduce tight coupling between business logic and database persistence engines.

### 4. Evolvability Fitness Function (EVOLVABLE)
- **Quality Attribute:** Extensibility Without Code Modification (Open/Closed Principle)
- **Fitness Function:** `test_ff_evolvability_zero_modification_subscriber_extension`
- **Measurement:** Registering a new third-party subscriber (e.g. `GridCarbonAuditor`) to `TradeMatchedEvent` during runtime and verifying message reception.
- **Threshold / Rule:** New subscribers must consume domain events without modifying existing publishers, simulators, or marketplace services.
- **Reason:** As the EcoGrid platform grows, new regulatory reporting, carbon offset accounting, and grid operator interfaces will need to be attached without risking regressions in core trading logic.

### 5. Resilience Fitness Function (RESILIENT)
- **Quality Attribute:** Fault Containment & Graceful Degradation
- **Fitness Function:** `test_ff_resilience_fault_isolation_and_dlq_containment`
- **Measurement:** Triggering an unhandled exception in one subscriber and verifying whether adjacent subscribers execute and whether the failed event is captured in the Dead Letter Queue.
- **Threshold / Rule:** A failing subscriber must never crash sibling subscribers or the event bus. Failed events must be recorded in the DLQ with error metadata after retries are exhausted.
- **Reason:** Distributed microservices and IoT platforms must remain operational even when individual downstream components crash.
