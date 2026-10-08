# EcoGrid Energy - Assessment Requirements Traceability Matrix

This document maps all core requirements from the **ICT711 Assessment 2** specification to their exact implementation artifacts, source files, and verification procedures.

---

## Traceability Matrix

| # | Assessment 2 Requirement | Architectural Implementation | Implementation File(s) | Verification Command & Procedure |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Separation of Marketplace & Smart Meter Ingestion** | Decoupled into independent bounded contexts. Smart meters publish `MeterReadingEvent` without calling Marketplace logic. | `smart_meter/simulator.py`<br/>`marketplace/service.py` | Run `python -m unittest tests.test_system.TestEcoGridSystem.test_bounded_context_isolation` |
| **2** | **High-Frequency IoT Event Ingestion** | Asynchronous non-blocking dispatch via `EventBus` processing 1,000+ meter readings at $>100$ readings/sec. | `shared/event_bus.py`<br/>`smart_meter/simulator.py` | Run `python scripts/performance_demo.py` |
| **3** | **Immutable Domain Event Contracts & Validation** | Frozen dataclasses with field-level `__post_init__` validation rejecting negative energy, invalid prices, and bad schemas. | `shared/models.py` | Run `python -m unittest tests.test_system.TestEcoGridSystem.test_domain_model_validation` |
| **4** | **P2P Matching Engine & Oversell Prevention** | FIFO price-compatible order matching algorithm with strict supply and demand reservation checks. | `marketplace/service.py` | Run `python -m unittest tests.test_system.TestEcoGridSystem.test_marketplace_no_overselling` |
| **5** | **Secure & Idempotent Financial Settlement** | Parameterized SQLite persistence (`?` placeholders) with table-level `UNIQUE(trade_id)` constraints and duplicate detection. | `settlement/service.py` | Run `python -m unittest tests.test_system.TestEcoGridSystem.test_settlement_idempotency` |
| **6** | **Resilience: Retry Policy & Dead Letter Queue** | Automatic retry loop (max 3 attempts) with backoff; exhausted failures quarantined into in-memory `DeadLetterQueue`. | `shared/event_bus.py` | Run `python scripts/failure_demo.py` |
| **7** | **Observability & Distributed Tracing** | Structured logging with domain event tags (`[METER_READING]`, `[TRADE_MATCHED]`) and `[CID: <uuid>]` correlation IDs. | `shared/logging_config.py` | Run `python main.py` and inspect console log tags and correlation IDs |
| **8** | **Fitness Function: Performance (FAST)** | Automated test verifying that a batch of 200 smart meter events executes in $< 2.0\text{s}$ ($>100\text{ events/sec}$). | `tests/test_fitness_functions.py` | Run `python -m unittest tests.test_fitness_functions.TestArchitecturalFitnessFunctions.test_ff_performance_high_frequency_throughput` |
| **9** | **Fitness Function: Security (SECURE)** | Automated test verifying input validation rejection and `.gitignore` exclusion of credentials and databases. | `tests/test_fitness_functions.py` | Run `python -m unittest tests.test_fitness_functions.TestArchitecturalFitnessFunctions.test_ff_security_input_validation_and_injection_immunity` |
| **10** | **Fitness Function: Maintainability (MAINTAINABLE)** | Reflection check ensuring `smart_meter` and `marketplace` have zero coupling to database persistence or `settlement`. | `tests/test_fitness_functions.py` | Run `python -m unittest tests.test_fitness_functions.TestArchitecturalFitnessFunctions.test_ff_maintainability_bounded_context_independence` |
| **11** | **Fitness Function: Evolvability (EVOLVABLE)** | Dynamic registration of a new subscriber (`GridCarbonAuditor`) to `TradeMatchedEvent` without modifying publishers. | `tests/test_fitness_functions.py` | Run `python -m unittest tests.test_fitness_functions.TestArchitecturalFitnessFunctions.test_ff_evolvability_zero_modification_subscriber_extension` |
| **12** | **Fitness Function: Resilience (RESILIENT)** | Test verifying subscriber fault containment and DLQ routing without crashing adjacent subscribers. | `tests/test_fitness_functions.py` | Run `python -m unittest tests.test_fitness_functions.TestArchitecturalFitnessFunctions.test_ff_resilience_fault_isolation_and_dlq_containment` |
| **13** | **Continuous Integration (CI/CD)** | GitHub Actions multi-version Python workflow running tests, bytecode validation, and demonstrations. | `.github/workflows/ci.yml` | Push to GitHub and view green Actions pipeline |
| **14** | **Domain-Driven Context Map** | Formal DDD context map documenting upstream/downstream relationships and Published Language contracts. | `docs/context-map.md` | Inspect Mermaid diagrams and relationship specifications |
| **15** | **Architectural Decision Records (ADRs)** | 4 standardized ADRs covering EDA, bounded contexts, eventual consistency, and SQLite selection. | `docs/adr/ADR-001` through `ADR-004` | Review ADR files in `docs/adr/` |
| **16** | **Trade-off Analysis** | Multi-dimensional comparison of Monolith, Microservices, and EDA across 11 architectural criteria. | `docs/tradeoffs.md` | Review comparative evaluation table |
| **17** | **Collaboration Evidence Support** | Exact checklist for capturing real GitHub, Monday.com, and communication tool screenshots. | `docs/collaboration-evidence-checklist.md` | Follow checklist to capture team screenshots |
| **18** | **Controlled AI Usage Evidence** | Controlled AI compliance guide with tracking template and 3 progressive refinement prompts. | `docs/ai-evidence-guide.md` | Review tracking table and execute suggested refinement prompts |
