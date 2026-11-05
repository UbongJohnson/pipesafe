# Portfolio 2: Query Processing and Optimisation

Eight business queries on the PipeSafe database are measured before and after optimisation, using PostgreSQL execution plans (`EXPLAIN ANALYZE`). They run on the real data (6,052 accidents) and on a scaled test copy (605,200 accidents).

**Main result:** searches became 6–68× faster at scale with the right indexes, and the "ten costliest accidents" report went from 2.7 seconds to 0.06 ms using a materialised view. The analysis also covers what each optimisation costs in storage, write speed and data freshness.

## Contents

| File | What it contains |
|---|---|
| `queries.sql` | The eight queries (Q1–Q8), each tied to a key operation from the case study |
| `queries_optimised.sql` | The same queries after optimisation: Q2 rewritten, plus Q2b and Q8b using the materialised view |
| `sql/01_setup_bench.sql` | Builds the scaled test copy (`bench` schema): every real row copied 100 times |
| `sql/02_optimise.sql` | Indexes, the rewritten summary view and the materialised view |
| `sql/03_undo.sql` | Removes the optimisations (returns to the baseline) |
| `sql/04_write_cost.sql` | Measures how much the new indexes slow down inserts |
| `scripts/benchmark.py` | Runs every query before and after, on both datasets; records median times and plans; checks results are identical |
| `results/timings.csv` | Median execution time and scan type for every query, dataset and phase |
| `results/<schema>_<phase>_<query>.txt` | Full `EXPLAIN (ANALYZE, BUFFERS)` output for each run (36 files) |
| `results/write_cost.txt` | Insert timings with and without the indexes |
| `performance-analysis.md` | **The write-up:** results, plan excerpts, explanations, trade-offs and conclusions |
| `screenshots/` | Evidence from your own machine |

## How to Run

Requirements: the Portfolio 1 database loaded (`pipesafe`), Python 3, and `pip install psycopg2-binary`.

```bash
cd portfolio-2-query-optimisation

# 1. Build the scaled test copy (about 10 seconds, about 1.3 GB of disk)
psql -d pipesafe -f sql/01_setup_bench.sql

# 2. Run the benchmark (about 2 minutes). Change the connection string to match your setup.
python scripts/benchmark.py "dbname=pipesafe user=postgres host=localhost password=YOUR_PASSWORD"

# 3. Measure the write cost of the indexes
psql -d pipesafe -f sql/04_write_cost.sql
```

To look at a single plan yourself:

```sql
SET search_path TO pipesafe, public;   -- or bench, public
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM accident WHERE operator_id = 31684 ORDER BY accident_datetime DESC;
```

## Results Summary (scaled copy, median ms)

| Query | Before | After | Change | Technique |
|---|---|---|---|---|
| Q3 Date range | 93 | 10 | 9× faster | B-tree index |
| Q4 One operator | 92 | 8 | 11× faster | Composite index (filter + sort) |
| Q6 Text search | 1,585 | 23 | 68× faster | Trigram GIN index |
| Q7 Corrosion detail | 165 | 25 | 6.5× faster | Foreign-key index |
| Q2b Top operators | 2,230 | 101 | 22× faster | Materialised view |
| Q8b Costliest accidents | 2,674 | 0.06 | 44,000× faster | Materialised view + index |
| Q1, Q5 Full summaries | 291, 227 | 292, 229 | No change | Indexes cannot help queries that read every row |

All optimised queries return exactly the same rows as the originals.

## Screenshots to Take

1. `EXPLAIN ANALYZE` for Q3 or Q4 before (Seq Scan) and after (Index Scan), side by side.
2. The terminal output of `benchmark.py`, showing the timings and "identical" checks.
3. The output of `04_write_cost.sql`.

Your times will differ from the ones above, because they depend on the machine. The before/after ratios should be similar.
