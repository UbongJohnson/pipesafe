# Performance Analysis: Query Processing and Optimisation

This document reports how eight business queries on the PipeSafe database performed before and after optimisation. It explains, using the execution plans, why each change helped or did not.

Every figure comes from `scripts/benchmark.py`. The full plans for every query are saved in `results/`.

## 1. Test Setup

| Item | Value |
|---|---|
| Database | PostgreSQL 16.15, default settings (`shared_buffers` 128 MB, `work_mem` 4 MB, up to 2 parallel workers) |
| Machine | 2 CPU cores, 7 GB RAM |
| Real data (`pipesafe`) | 6,052 accidents, 36,261 cost rows |
| Scaled copy (`bench`) | 605,200 accidents, 3,626,100 cost rows: every real row copied 100 times (`sql/01_setup_bench.sql`) |
| Measurement | Each query run twice to warm the cache, then `EXPLAIN (ANALYZE, BUFFERS)` 7 times; the **median** execution time is reported |
| Correctness check | Every optimised query was confirmed to return **exactly the same rows** as the original, on both datasets |

**Why a scaled copy?** The real database is small: the whole `accident` table is 6.6 MB and fits in memory. At that size PostgreSQL can read every row in about a millisecond, so index benefits are real but tiny. The scaled copy shows how the same queries behave at production size.

Copying rows keeps realistic value distributions (41% of accidents are still in Texas), but it is not real data. It is used only for performance testing.

Absolute timings will differ on other machines. The ratios between "before" and "after" are the meaningful result.

## 2. What Was Optimised

| Technique | Applied to | File |
|---|---|---|
| B-tree indexes on foreign-key and filter columns | Q3, Q4, Q5, Q7 | `sql/02_optimise.sql` |
| Composite index matching filter **and** sort order | Q4 | `sql/02_optimise.sql` |
| Trigram (GIN) index for `ILIKE '%…%'` text search | Q6 | `sql/02_optimise.sql` |
| Query rewrite: aggregate first, then join | Q2 | `queries_optimised.sql` |
| View rewrite: replace correlated subqueries with joins | Q8 | `sql/02_optimise.sql` |
| Materialised view of pre-calculated totals | Q2b, Q8b | `sql/02_optimise.sql` |

**Starting point:** PostgreSQL automatically indexes primary keys, but **not foreign keys**. None of the `accident` table's foreign-key columns had an index, so every "before" plan reads the whole `accident` table (a `Seq Scan`).

## 3. Results

### Median execution time (ms)

| Query | Business question | Real before | Real after | Speed-up | Scaled before | Scaled after | Speed-up |
|---|---|---|---|---|---|---|---|
| Q1 | Accidents per year by cause | 4.12 | 4.31 | none | 290.97 | 291.93 | none |
| Q2 | Top 10 operators by cost (rewrite) | 28.95 | 13.18 | 2.2× | 2,229.93 | 1,704.43 | 1.3× |
| Q2b | Same, from materialised view | 28.95 | 2.05 | 14× | 2,229.93 | 100.98 | **22×** |
| Q3 | Texas accidents in 2023 | 1.06 | 0.20 | 5.3× | 93.46 | 10.31 | **9.1×** |
| Q4 | One operator's history | 0.76 | 0.13 | 5.8× | 92.31 | 8.19 | **11×** |
| Q5 | Recovery rate by commodity | 3.64 | 3.66 | none | 227.19 | 228.71 | none |
| Q6 | Narrative text search | 32.16 | 0.30 | 107× | 1,584.55 | 23.40 | **68×** |
| Q7 | Unprotected external corrosion | 1.85 | 0.46 | 4.0× | 164.50 | 25.20 | **6.5×** |
| Q8 | Ten costliest accidents (view rewrite) | 37.90 | 17.96 | 2.1× | 2,673.76 | 2,117.01 | 1.3× |
| Q8b | Same, from materialised view | 37.90 | 0.07 | 541× | 2,673.76 | 0.06 | **44,000×** |

### Scan used on the `accident` table

| Query | Before | After |
|---|---|---|
| Q1, Q5 | Seq Scan | Seq Scan (unchanged) |
| Q3 | Seq Scan | Index Scan (`idx_accident_datetime`) |
| Q4 | Seq Scan | Bitmap Heap Scan (`idx_accident_operator_date`) |
| Q6 | Seq Scan | Bitmap Heap Scan (`idx_accident_narrative_trgm`) |
| Q7 | Seq Scan | Bitmap Heap Scan |
| Q8b | Seq Scan | Index Scan on the materialised view, then 10 primary-key lookups |

## 4. Query-by-Query Explanation

### Q3: Date range (index scan replaces full scan)

**Before** (real data): PostgreSQL read all 6,052 rows and threw away 5,753 of them.
```
Seq Scan on accident a  (actual time=0.729..0.919 rows=299 loops=1)
  Filter: ((accident_datetime >= '2023-01-01') AND (accident_datetime < '2024-01-01'))
  Rows Removed by Filter: 5753
  Buffers: shared hit=832
```
**After:** the index on `accident_datetime` goes straight to the 299 rows in 2023, reading 175 pages instead of 832.
```
Index Scan Backward using idx_accident_datetime on accident a  (actual time=0.003..0.048 rows=299 loops=1)
  Index Cond: ((accident_datetime >= '2023-01-01') AND (accident_datetime < '2024-01-01'))
  Buffers: shared hit=175
```
The scan is *backward* because the query sorts newest first. PostgreSQL reads the index in reverse instead of sorting.

### Q4: One operator (composite index)

The index `(operator_id, accident_datetime DESC)` serves both the filter and the sort order. On the scaled copy, the full scan read **81,392 pages** across three parallel workers and discarded 194,567 rows per worker. The index read **3,081 pages**, and the time fell from 92 ms to 8 ms.

### Q6: Text search (trigram index)

`narrative ILIKE '%frozen%'` cannot use a normal B-tree index, because the pattern **starts** with a wildcard. A B-tree only helps when the beginning of the value is known.

A trigram index splits text into three-letter pieces ("fro", "roz", "oze"…), so any substring can be found. On the scaled copy, the full scan read 118,000 pages of narrative text. The trigram index found the 3,600 matches by reading 86 index pages, and the time fell from 1,585 ms to 23 ms.
```
Bitmap Index Scan on idx_accident_narrative_trgm  (actual time=0.876..0.876 rows=3600 loops=1)
  Index Cond: (narrative ~~* '%frozen%'::text)
  Buffers: shared hit=86
```

### Q7: Selective join

Only corrosion accidents with a specific answer are needed. With indexes on the join columns, PostgreSQL fetches just those accidents (Bitmap Heap Scan) instead of reading the whole table. It was 6.5× faster on the scaled copy.

### Q1 and Q5: Where indexes do *not* help

Both queries summarise **every** accident: counts per year and recovery rate per commodity. When a query needs every row, reading the table in order is the cheapest way. An index would add a lookup per row on top of reading the same data.

PostgreSQL's planner correctly ignored the new indexes for these queries (Q1 does not use `idx_accident_cause_detail`, and no query used `idx_accident_commodity`), and the times did not change. **An index only helps when a query needs a small fraction of the rows.**

### Q2 and Q8: Rewrites help, but not enough at scale

**Q2 rewrite.** The original query joined 3.6 million cost rows to accidents, then used `COUNT(DISTINCT report_number)`, which forces a large sort. The rewrite totals each accident's costs first and then joins. This halved the time on the real data, but saved only 23% on the scaled copy.

**Q8 view rewrite.** The original summary view ran three correlated subqueries for each of the 605,200 accidents; the planner's cost estimate was 17 million. The rewritten view aggregates costs and casualties once each and joins the results. This halved the time on the real data, but saved only 21% on the scaled copy.

**Why the gains are small at scale:** both queries must still add up all 3.6 million cost rows, which takes about 1.4 seconds in the plan (`GroupAggregate … rows=602991 loops=3`). An index cannot avoid reading data that the answer depends on.

### Q2b and Q8b: Materialised view

`mv_accident_totals` stores each accident's total cost, fatalities and injuries, calculated once. It has an index on `total_cost_usd DESC`.

- **Q8b** reads the first 10 entries of that index (4 pages), then looks up those 10 accidents by primary key. The whole query reads 85 pages and takes **0.06 ms instead of 2,674 ms**.
- **Q2b** sums 605,200 stored totals instead of 3.6 million cost rows, taking **101 ms instead of 2,230 ms**.

```
Limit  (actual time=0.003..0.005 rows=10 loops=1)
  ->  Index Scan using mv_accident_totals_cost on mv_accident_totals  (actual time=0.003..0.004 rows=10 loops=1)
        Buffers: shared hit=4
```

## 5. The Cost of Optimisation

Every optimisation trades something for read speed.

### Storage (scaled copy)

| Object | Size |
|---|---|
| `accident` table | 635 MB |
| Trigram index on narrative | **307 MB** (almost half the table) |
| Materialised view and its two indexes | 71 MB |
| Each B-tree index | about 4 MB |

The B-tree indexes are unusually small because each value appears 100 times in the scaled copy, and PostgreSQL 13+ stores repeated index values only once (deduplication). With 605,200 genuinely different accidents they would be larger.

### Write speed (`sql/04_write_cost.sql`, `results/write_cost.txt`)

Inserting 6,052 new accidents into the scaled copy (median of 3 runs):

| Indexes present | Insert time |
|---|---|
| None of the new indexes | 41 ms |
| Five new B-tree indexes | 76 ms |
| Five B-tree + trigram index | **1,805 ms** |

The five B-tree indexes nearly double write time, which is acceptable. The trigram index makes inserts **about 24 times slower than with the B-trees alone**, because every narrative of about 950 characters generates hundreds of trigram entries.

### Freshness

The materialised view is a snapshot. New reports do not appear in it until it is refreshed:

| Dataset | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (median of 3) |
|---|---|
| Real (6,052 accidents) | 50 ms |
| Scaled (605,200 accidents) | 3,289 ms |

`CONCURRENTLY` lets users keep reading the old snapshot while it refreshes. It requires the unique index `mv_accident_totals_pk`.

### Is each trade-off worth it for PipeSafe?

| Optimisation | Decision | Reason |
|---|---|---|
| `idx_accident_operator_date`, `idx_accident_datetime`, `idx_accident_cause_detail` | **Keep** | Large read gains for searches (Q3, Q4, Q7) at a small write cost |
| Trigram index | **Keep** | Accident reports arrive a few hundred per year (about 6,000 in 16 years), so slower inserts do not matter. Narrative search is used constantly by analysts and investigators. |
| `idx_accident_county`, `idx_accident_commodity` | **Drop** | Neither was used by any of the eight queries (checked in every saved plan), so they only add write cost and storage. They would be worth re-adding if counties or commodity subtypes were ever deleted often, because PostgreSQL then checks `accident` for rows still referencing them. |
| Rewritten summary view | **Keep** | Never slower, about 2× faster on real data, same results |
| Materialised view | **Keep, refreshed nightly** (or after each batch of reports) | Dashboards and "top 10" reports become instant. Data up to a day old is acceptable for trend reports. Live search queries still use the normal tables. |

## 6. Conclusions

1. **Missing foreign-key indexes are a common avoidable cost, but only where queries filter or join selectively on them.** PostgreSQL does not create them automatically. The right ones, plus one composite index matched to the filter and sort, gave 6–11× gains on searches. Two of the six new indexes were never used, which is why each index should be checked against real plans before it is kept.
2. **Indexes only help selective queries.** Q1 and Q5 read every row, so no index can help, and the planner rightly ignored them.
3. **Specialised index types solve problems B-trees cannot.** The trigram index made substring search 68–107× faster, at a real cost in storage and write speed.
4. **For totals over millions of rows, pre-calculation beats indexing.** A materialised view made the "ten costliest accidents" report 44,000× faster, at the cost of a scheduled refresh.
5. **Small data hides problems.** On 6,052 rows every query took under 40 ms before optimisation. Only the scaled copy showed which designs would not survive growth.

## 7. How to Reproduce

From this folder, with the Portfolio 1 database loaded:

```bash
psql -d pipesafe -f sql/01_setup_bench.sql      # build the scaled copy (~10 s)
python scripts/benchmark.py "dbname=pipesafe"   # before/after timings for both datasets
psql -d pipesafe -f sql/04_write_cost.sql       # write-cost test
```

`benchmark.py` applies `sql/03_undo.sql` (baseline) and `sql/02_optimise.sql` (optimised) itself. It writes `results/timings.csv` and one plan file per query, schema and phase.
