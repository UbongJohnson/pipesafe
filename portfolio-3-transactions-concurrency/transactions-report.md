# Transactions and Concurrency in PipeSafe

PipeSafe's users work on the same accident reports at the same time. Operators file new reports, and investigators update open reports as clean-up progresses. This portfolio shows how PostgreSQL transactions keep that data correct, what goes wrong without the right controls, and how each problem is fixed.

Every result below comes from running the scripts in this folder against the real Portfolio 1 database. The output is saved in `results/`.

**Test data.** Demos that change data use clearly marked test reports, numbered `99990001`, `99990002`, `99990010` and so on. Real PHMSA report numbers start with the year (e.g. `20260244`). Test reports are created by `sql/00_setup_test_data.sql` and removed by `sql/99_cleanup.sql`. After clean-up the database has its original 6,052 accidents (`results/99_cleanup.log`).

---

## 1. Why Transactions Matter Here

Logging one accident writes to **four tables**: `accident`, `accident_cost`, `casualty` and a cause-detail table. If the system failed halfway, the database could hold an accident with no costs, or costs belonging to no accident. A transaction groups these writes so they succeed or fail **as one unit**.

The four ACID properties, as they apply to PipeSafe:

| Property | Meaning | Where it is shown |
|---|---|---|
| **Atomicity** | All of a transaction's changes are saved, or none are | Demos 1, 2 |
| **Consistency** | A transaction cannot leave the data breaking a rule (keys, CHECK constraints) | Demos 2, 7 |
| **Isolation** | Concurrent transactions do not see each other's half-finished work; the level is configurable | Demos 4–6 |
| **Durability** | Once `COMMIT` returns, the change survives a crash (PostgreSQL's write-ahead log) | Implied by every `COMMIT`; replication in Portfolio 5 builds on the same log |

---

## 2. Single-Session Demos

### Demo 1: COMMIT — logging a new accident (`sql/01_commit.sql`)

Report 99990010 is inserted with 3 cost rows, 1 casualty and its corrosion details, between `BEGIN` and `COMMIT`. Afterwards, all four tables contain it:

```
    table_name    | count
------------------+-------
 accident         |     1
 accident_cost    |     3
 casualty         |     1
 corrosion_detail |     1
```
The summary view immediately shows the new report: total cost $108,800, 1 injury, cause "CORROSION FAILURE".

### Demo 2: Automatic ROLLBACK on error (`sql/02_rollback_on_error.sql`)

**Example A.** The accident row is inserted successfully. Then a cost of –$5,000 breaks the CHECK constraint `amount_usd >= 0`:
```
ERROR:  new row for relation "accident_cost" violates check constraint "accident_cost_amount_usd_check"
ERROR:  current transaction is aborted, commands ignored until end of transaction block
COMMIT;
ROLLBACK
```
Three things to notice:
- After the error, PostgreSQL refuses every further statement in the transaction.
- `COMMIT` is turned into `ROLLBACK`.
- The **accident row that had already been inserted is gone as well**: `rows_for_99990011 = 0`.

This is **atomicity**. There is no half-logged accident.

**Example B.** An update setting recovered oil to 650 barrels on a report where only 500 were released is rejected by the business rule `chk_recovered_not_more_than_released`. This is **consistency**: no transaction can save data that breaks the rules.

### Demo 3: Explicit ROLLBACK and SAVEPOINT (`sql/03_explicit_rollback_and_savepoint.sql`)

**Explicit ROLLBACK.** An analyst means to close one report but forgets the report number in the `WHERE` clause. The update closes **all 124 open ORIGINAL reports** (121 real ones plus the 3 test reports). Inside the transaction the count of open reports drops to 0, but nobody else can see this. `ROLLBACK` restores all 124, as if the mistake never happened.

**SAVEPOINT.** Within one transaction:
1. A valid update sets recovered oil to 320 bbl.
2. `SAVEPOINT before_casualty`.
3. An invalid casualty group `'VISITOR'` fails its CHECK constraint.
4. `ROLLBACK TO SAVEPOINT before_casualty` undoes **only** that insert.
5. A corrected insert (`'PUBLIC'`) succeeds, then `COMMIT`.

Result: the update from step 1 and the corrected casualty are both saved. A savepoint allows recovery from one failed step without losing the rest of the work.

---

## 3. Two-Session Concurrency Demos

`scripts/concurrency_demo.py` opens two database sessions, **A** and **B**, representing two investigators. It runs their statements in a fixed order. Statements that must wait for a lock run in a background thread, so the waiting is visible in the timestamps. The full transcript is in `results/concurrency_demo.log`.

The starting point for most scenarios is test report 99990001, with **500 bbl released and 300 bbl recovered**.

### Isolation levels

PostgreSQL's default level is **READ COMMITTED**: each *statement* sees the latest committed data. Under **REPEATABLE READ**, the whole *transaction* sees one fixed snapshot, taken at its first query.

#### Demo 4: Non-repeatable read (scenarios 1a and 1b)

A reads the recovered volume twice in one transaction. Between the two reads, B changes it to 350 and commits.

| Isolation level | A's first read | A's second read | Outcome |
|---|---|---|---|
| READ COMMITTED | 300 | **350** | Same query, different answer in one transaction |
| REPEATABLE READ | 300 | 300 | Stable snapshot |

This matters for reports: a summary that reads a figure twice, such as in a total and then in a percentage, could contradict itself under READ COMMITTED.

#### Demo 5: Phantom read (scenarios 2a and 2b)

A counts Phillips 66's open reports twice. In between, B files a new report.

| Isolation level | First count | Second count | Outcome |
|---|---|---|---|
| READ COMMITTED | 4 | **5** | A "phantom" row appears |
| REPEATABLE READ | 4 | 4 | No phantom |

In PostgreSQL, REPEATABLE READ also prevents phantoms. The SQL standard only requires this at SERIALIZABLE.

### The lost update problem and three fixes

#### Demo 6: LOST UPDATE — the problem (scenario 3)

Two investigators each recover more oil: A recovers 50 bbl and B recovers 30 bbl. Each application **reads** the current total, **adds** its amount, and **writes** the new total back. This is a read-modify-write pattern.

```
A> SELECT recovered_bbls ...      -> 300.00
B> SELECT recovered_bbls ...      -> 300.00
A> UPDATE ... SET recovered_bbls = 350.00
A> COMMIT
B> UPDATE ... SET recovered_bbls = 330.00
B> COMMIT
RESULT: recovered_bbls = 330.00  (WRONG - A's 50 barrels were silently overwritten)
```
The correct total is 380. **No error was raised.** B's write was based on a value that was already out of date, and the default isolation level does not detect this. In a regulatory database, this means under-reporting 50 barrels of recovered oil.

#### Fix 1: Pessimistic locking with `SELECT ... FOR UPDATE` (scenario 4)

A locks the row as it reads it. B's `SELECT ... FOR UPDATE` **waits**. The log shows that B waited 2.00 s, until A committed. B then reads A's new value, 350, and writes 380.

**Result: 380 (correct).** This is best when conflicts are likely and waiting is acceptable.

#### Fix 2: REPEATABLE READ, which detects the conflict (scenario 5)

Neither session locks anything when reading. When B tries to update a row that changed after B's snapshot was taken, PostgreSQL refuses:
```
B> UPDATE accident SET recovered_bbls = 330.00 ...
   ERROR:  could not serialize access due to concurrent update
```
The application rolls back and **retries** B's transaction. The retry reads 350 and writes 380.

**Result: 380 (correct).** This is an *optimistic* approach: no waiting, but the application must be written to retry.

#### Fix 3: One atomic UPDATE (scenario 6)

The addition is done inside the database, with no separate read:
```sql
UPDATE accident SET recovered_bbls = recovered_bbls + 30 WHERE report_number = 99990001;
```
B's update waits for A's row lock, then re-applies `+ 30` to the latest committed value.

**Result: 380 (correct).** This is the simplest and fastest fix when the change can be expressed as one statement.

#### Comparison

| Approach | Correct result? | Cost | Best for |
|---|---|---|---|
| Read-modify-write, READ COMMITTED | **No** (330) | — | Never, for shared counters or totals |
| `SELECT ... FOR UPDATE` | Yes (380) | Second user waits | Multi-step edits where conflicts are common |
| REPEATABLE READ + retry | Yes (380) | Work repeated on conflict; needs retry logic | Conflicts are rare |
| Atomic `UPDATE x = x + n` | Yes (380) | None | Simple increments |

**PipeSafe's choice:** increments to recovered volumes and costs use atomic updates. Editing a whole report form, where an investigator reads, reviews and then saves, uses `SELECT ... FOR UPDATE` on that report.

### Demo 7: Locking and constraints together (scenario 7)

500 bbl were released and 300 recovered. A records +150 and B records +100, which together would come to 550, more than was released.

With locking, B waits, reads A's value of 450, and tries to write 550. The CHECK constraint refuses:
```
ERROR:  new row for relation "accident" violates check constraint "chk_recovered_not_more_than_released"
```
The final value is 450. B's impossible figure was refused, so B's investigator knows to re-check their measurement.

**Without locking,** B would have written 300 + 100 = 400. That passes the CHECK while silently losing A's 150 barrels. A constraint only protects data reliably when concurrent updates are controlled.

### Deadlock and its fix

#### Demo 8: DEADLOCK — the problem (scenario 8)

A updates report 99990001 and then 99990002. B updates the same reports in the **opposite** order. Each session holds one row lock and waits for the other's:
```
[0.00s] A> UPDATE ... report_number = 99990002     (waits for B)
[0.30s] B> UPDATE ... report_number = 99990001     (waits for A)
           A  -> ERROR:  deadlock detected
[1.00s] A> ROLLBACK
[1.00s] B> COMMIT
```
After `deadlock_timeout` (1 second), PostgreSQL's deadlock detector found the cycle and cancelled session A so that B could finish. Nothing is corrupted, but A's work is lost and has to be redone.

#### Fix: Lock rows in a consistent order (scenario 9)

Both sessions first lock **all** the rows they need, always in the same order (`ORDER BY report_number FOR UPDATE`):
```sql
SELECT report_number FROM accident
WHERE report_number IN (99990001, 99990002)
ORDER BY report_number FOR UPDATE;
```
B now waits for A at the start instead of halfway through. A finishes, then B runs.

**Result: both reports go from 300 to 302, and there is no deadlock.** A cycle cannot form when everyone acquires locks in the same order.

---

## 4. Choices for PipeSafe

| Situation | Control used |
|---|---|
| Logging a new accident (four tables) | One transaction: all rows or none |
| Adding recovered volume or a cost to an open report | Atomic `UPDATE … = … + n` |
| An investigator editing a full report form | `SELECT … FOR UPDATE` on that report, then update |
| Trend reports and dashboards | `REPEATABLE READ`, so every figure comes from one consistent snapshot |
| Updating several reports in one job | Lock them in `report_number` order to prevent deadlocks |
| All writes | CHECK constraints as the last line of defence |

## 5. How to Run

```bash
cd portfolio-3-transactions-concurrency
psql -d pipesafe -f sql/00_setup_test_data.sql
psql -d pipesafe -e -f sql/01_commit.sql
psql -d pipesafe -e -f sql/02_rollback_on_error.sql
psql -d pipesafe -e -f sql/03_explicit_rollback_and_savepoint.sql
python scripts/concurrency_demo.py "dbname=pipesafe user=postgres host=localhost password=YOUR_PASSWORD"
psql -d pipesafe -f sql/99_cleanup.sql
```

## 6. Doing a Demo by Hand (for Screenshots)

Open **two** psql windows (or two pgAdmin Query Tool tabs), both connected to `pipesafe`. Run `SET search_path TO pipesafe;` in each, and run `00_setup_test_data.sql` once. Then follow the steps in order, switching windows as shown.

**Lost update:**

| Step | Window A | Window B |
|---|---|---|
| 1 | `BEGIN;` | |
| 2 | | `BEGIN;` |
| 3 | `SELECT recovered_bbls FROM accident WHERE report_number = 99990001;` → 300 | |
| 4 | | same `SELECT` → 300 |
| 5 | `UPDATE accident SET recovered_bbls = 350 WHERE report_number = 99990001; COMMIT;` | |
| 6 | | `UPDATE accident SET recovered_bbls = 330 WHERE report_number = 99990001; COMMIT;` |
| 7 | `SELECT recovered_bbls …` → **330** (A's +50 lost) | |

**FOR UPDATE fix:** reset with `UPDATE accident SET recovered_bbls = 300 WHERE report_number = 99990001;`. Repeat the steps, adding `FOR UPDATE` to both `SELECT`s. At step 4, window B **freezes** until A commits at step 5. B then shows 350, so it should write 380.

**Deadlock:**

| Step | Window A | Window B |
|---|---|---|
| 1 | `BEGIN; UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = 99990001;` | |
| 2 | | `BEGIN; UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = 99990002;` |
| 3 | `UPDATE … WHERE report_number = 99990002;` (waits) | |
| 4 | | `UPDATE … WHERE report_number = 99990001;` → one window shows `ERROR: deadlock detected` after about 1 s |
| 5 | `ROLLBACK;` in the failed window, `COMMIT;` in the other | |

Run `99_cleanup.sql` when you are finished.
