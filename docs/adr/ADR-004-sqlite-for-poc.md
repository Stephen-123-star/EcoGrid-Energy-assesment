# ADR-004: Selection of SQLite for Proof-of-Concept Financial Persistence

## Status
**Accepted**

## Context
The EcoGrid Energy proof-of-concept must demonstrate secure, ACID-compliant persistence for matched financial micro-transactions without introducing heavy infrastructure dependencies (such as managed PostgreSQL clusters or distributed Cloud Spanner instances) that would complicate academic reproducibility, continuous integration, and local testing.

## Decision
We selected **Python's standard library `sqlite3`** engine for the financial settlement ledger in this proof-of-concept:
- Persistence is stored locally in `data/ecogrid.db` or temporary in-memory databases during automated testing (`:memory:` or temporary files).
- All queries strictly utilize parameterized SQL placeholders (`?`) to prevent SQL injection vulnerabilities.
- Table schemas enforce `PRIMARY KEY` and `UNIQUE` constraints on `trade_id` to guarantee database-level idempotency.

## Consequences

### Positive (Benefits)
- **Zero External Dependencies:** Runs immediately in any standard Python 3.10+ runtime without requiring Docker, database servers, or cloud credentials.
- **Fast and Isolated Automated Testing:** Unit and integration tests spin up temporary, isolated SQLite instances in milliseconds, guaranteeing zero side-effects between test runs.
- **ACID Guarantees:** Supports atomic transactions (`BEGIN`, `COMMIT`, `ROLLBACK`) for micro-settlement records.

### Negative (Trade-offs & Production Differences)
- **Concurrency Limitations:** SQLite uses file-level locking during write operations, which is unsuitable for massive multi-node production scale.
- **Production Replacement Required:** In a production deployment, this context must migrate to a distributed, horizontally scalable database (such as PostgreSQL with connection pooling, CockroachDB, or AWS Aurora PostgreSQL).
