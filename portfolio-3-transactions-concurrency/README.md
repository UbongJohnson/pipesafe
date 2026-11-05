# Portfolio 3: Transactions and Concurrency

This portfolio shows commit, rollback, savepoints, isolation levels, and three concurrency problems (non-repeatable and phantom reads, lost updates, deadlocks), each with working fixes. Everything runs against the PipeSafe database from Portfolio 1.

Demos that change data use clearly marked test reports (numbers starting `9999`), which are removed afterwards. Real data is never altered.

## Contents

| File | What it contains |
|---|---|
| `sql/00_setup_test_data.sql` | Creates two open test reports (500 bbl released, 300 recovered) |
| `sql/01_commit.sql` | Logs a new accident across four tables in one transaction |
| `sql/02_rollback_on_error.sql` | A CHECK violation rolls back the whole transaction (atomicity), plus a business-rule rejection |
| `sql/03_explicit_rollback_and_savepoint.sql` | Undoing a mistaken mass update; partial rollback with `SAVEPOINT` |
| `sql/99_cleanup.sql` | Removes the test reports; confirms 6,052 accidents remain |
| `scripts/concurrency_demo.py` | Two sessions (A and B) running 9 concurrency scenarios in a fixed order |
| `results/*.log` | Output of every script (`psql -e`, so each statement is shown before its result) |
| `results/concurrency_demo.log` | Full timestamped transcript of the two-session scenarios |
| `transactions-report.md` | **The write-up:** each demo, its output and what it proves, plus the controls chosen for PipeSafe |
| `screenshots/` | Evidence from your own machine |

## Results Summary

| Scenario | Outcome |
|---|---|
| Commit across 4 tables | All rows saved together |
| Error mid-transaction | Whole transaction rolled back, including rows inserted before the error |
| Savepoint | Only the failed step undone; the rest committed |
| Non-repeatable read | READ COMMITTED: 300 then 350 · REPEATABLE READ: 300 then 300 |
| Phantom read | READ COMMITTED: 4 then 5 · REPEATABLE READ: 4 then 4 |
| Lost update | **330** instead of 380, with no error |
| Fix: `SELECT … FOR UPDATE` | 380 (B waited 2 s) |
| Fix: REPEATABLE READ + retry | "could not serialize access", then retry, giving 380 |
| Fix: atomic `UPDATE x = x + n` | 380 |
| Locking + CHECK | Over-recovery refused instead of silently lost |
| Deadlock | Detected after 1 s; one session cancelled |
| Fix: consistent lock order | No deadlock; both updates applied |

## How to Run

Requirements: the Portfolio 1 database, Python 3, and `pip install psycopg2-binary`.

```bash
cd portfolio-3-transactions-concurrency
psql -d pipesafe -f sql/00_setup_test_data.sql
psql -d pipesafe -e -f sql/01_commit.sql
psql -d pipesafe -e -f sql/02_rollback_on_error.sql
psql -d pipesafe -e -f sql/03_explicit_rollback_and_savepoint.sql
python scripts/concurrency_demo.py "dbname=pipesafe user=postgres host=localhost password=YOUR_PASSWORD"
psql -d pipesafe -f sql/99_cleanup.sql
```

## Screenshots to Take

1. The output of `02_rollback_on_error.sql`, showing the error and `rows_for_99990011 = 0`.
2. **Two psql windows side by side**: the lost update, then the `FOR UPDATE` version with window B waiting. Step-by-step instructions are in section 6 of `transactions-report.md`.
3. Both windows during the deadlock demo, showing `ERROR: deadlock detected`.
