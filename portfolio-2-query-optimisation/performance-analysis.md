# Performance Analysis: Query Processing and Optimisation

This document reports how eight business queries on the PipeSafe database performed before and after optimisation. It explains, using the execution plans, why each change helped or did not.

Every figure comes from `scripts/benchmark.py`. The full plans for every query are saved in `results/`.

## 1. Test Setup

| Item | Value |
|---|---|
| Database | PostgreSQL 18.0 on Windows 11, default settings (`shared_buffers` 128 MB, `work_mem` 4 MB, up to 2 parallel workers) |
| Machine | Intel Core i7-6500U laptop: 2 CPU cores (4 threads), 8 GB RAM |
| Real data (`pipesafe`) | 6,052 accidents, 36,261 cost rows |
| Scaled copy (`bench`) | 605,200 accidents, 3,626,100 cost rows: every real row copied 100 times (`sql/01_setup_bench.sql`) |
| Measurement | Each query run twice to warm the cache, then `EXPLAIN (ANALYZE, BUFFERS)` 7 times; the **median** execution time is reported |
| Correctness check | Every optimised query was confirmed to return **exactly the same rows** as the original, on both datasets |

**Why a scaled copy?** The real database is small: the whole `accident` table is 15 MB including all its indexes and fits in memory. At that size PostgreSQL can read every row in about a millisecond, so index benefits are real but tiny. The scaled copy shows how the same queries behave at production size.

Copying rows keeps realistic value distributions (41% of accidents are still in Texas), but it is not real data. It is used only for performance testing.

Absolute timings will differ on other machines. The ratios between "before" and "after" are the meaningful result.

**Why the scaled timings are high.** The scaled `accident` table's data (about 636 MB) is about five times larger than PostgreSQL's 128 MB buffer cache. A full scan therefore reads most pages from disk: the Q4 scan, for example, found 5,714 pages in memory and read 75,640 from disk. This makes every full scan slow and somewhat variable, and it makes indexes more valuable, because each page an index avoids is usually a disk read avoided.

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
| Q1 | Accidents per year by cause | 23.04 | 24.16 | none (same plan) | 1,284.49 | 2,203.18 | none (same plan)¹ |
| Q2 | Top 10 operators by cost (rewrite) | 117.52 | 69.01 | 1.7× | 20,629.87 | 8,940.89 | 2.3× |
| Q2b | Same, from materialised view | 117.52 | 5.42 | 22× | 20,629.87 | 609.48 | **34×** |
| Q3 | Texas accidents in 2023 | 4.55 | 1.02 | 4.5× | 2,097.39 | 46.04 | **46×** |
| Q4 | One operator's history | 3.11 | 0.62 | 5.0× | 1,632.21 | 37.97 | **43×** |
| Q5 | Recovery rate by commodity | 19.80 | 14.59 | none (same plan)¹ | 1,196.71 | 1,336.43 | none (same plan) |
| Q6 | Narrative text search | 186.48 | 1.79 | 104× | 8,838.18 | 179.43 | **49×** |
| Q7 | Unprotected external corrosion | 6.68 | 1.49 | 4.5× | 744.28 | 145.79 | **5.1×** |
| Q8 | Ten costliest accidents (view rewrite) | 102.36 | 75.64 | 1.4× | 49,370.18 | 20,539.51 | 2.4× |
| Q8b | Same, from materialised view | 102.36 | 0.30 | 341× | 49,370.18 | 0.35 | **about 140,000×** |

¹ Q1 and Q5 used exactly the same plan before and after, reading the same pages. The differences (Q1 slower on the scaled copy, Q5 faster on the real data) come from disk-read variation, not from the optimisation. See "Q1 and Q5" below.

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
Seq Scan on accident a  (actual time=8.956..9.770 rows=299.00 loops=1)
  Filter: ((accident_datetime >= '2023-01-01') AND (accident_datetime < '2024-01-01'))
  Rows Removed by Filter: 5753
  Buffers: shared hit=832
```
**After:** the index on `accident_datetime` goes straight to the 299 rows in 2023, reading 173 pages instead of 832.
```
Index Scan Backward using idx_accident_datetime on accident a  (actual time=0.015..0.176 rows=299.00 loops=1)
  Index Cond: ((accident_datetime >= '2023-01-01') AND (accident_datetime < '2024-01-01'))
  Buffers: shared hit=173
```
The scan is *backward* because the query sorts newest first. PostgreSQL reads the index in reverse instead of sorting.

### Q4: One operator (composite index)

The index `(operator_id, accident_datetime DESC)` serves both the filter and the sort order. On the scaled copy, the full scan read **81,354 pages** (75,640 of them from disk) across three parallel workers and discarded 194,567 rows per worker. The index read **3,081 pages**, all already in memory, and the time fell from 1,632 ms to 38 ms.

### Q6: Text search (trigram index)

`narrative ILIKE '%frozen%'` cannot use a normal B-tree index, because the pattern **starts** with a wildcard. A B-tree only helps when the beginning of the value is known.

A trigram index splits text into three-letter pieces ("fro", "roz", "oze"…), so any substring can be found. On the scaled copy, the full scan read 118,038 pages of narrative text (70,557 from disk). The trigram index found the 3,600 matches by reading 85 index pages, and the time fell from 8,838 ms to 179 ms.
```
Bitmap Index Scan on idx_accident_narrative_trgm  (actual time=5.257..5.258 rows=3600.00 loops=1)
  Index Cond: (narrative ~~* '%frozen%'::text)
  Buffers: shared hit=85
```

### Q7: Selective join

Only corrosion accidents with a specific answer are needed. With indexes on the join columns, PostgreSQL fetches just those accidents (Bitmap Heap Scan) instead of reading the whole table. It was 5.1× faster on the scaled copy.

### Q1 and Q5: Where indexes do *not* help

Both queries summarise **every** accident: counts per year and recovery rate per commodity. When a query needs every row, reading the table in order is the cheapest way. An index would add a lookup per row on top of reading the same data.

PostgreSQL's planner correctly ignored the new indexes for these queries (Q1 does not use `idx_accident_cause_detail`, and no query used `idx_accident_commodity`), so the plans did not change. **An index only helps when a query needs a small fraction of the rows.**

The measured times did move, in both directions: Q1 on the scaled copy took 1,284 ms before and 2,203 ms after. Both runs used the identical plan and read the same 81,316 pages, about 71,500 of them from disk. The difference is how quickly the disk delivered those pages during each run, not the optimisation. This is a reminder to compare plans and pages read, not only times, when the data does not fit in memory.

### Q2 and Q8: Rewrites help, but not enough at scale

**Q2 rewrite.** The original query joined 3.6 million cost rows to accidents, then used `COUNT(DISTINCT report_number)`, which forces a large sort. The rewrite totals each accident's costs first and then joins. This saved 41% on the real data and 57% on the scaled copy, but the scaled query still took 8.9 seconds.

**Q8 view rewrite.** The original summary view ran three correlated subqueries for each of the 605,200 accidents; the planner's cost estimate was 17 million. The rewritten view aggregates costs and casualties once each and joins the results (estimate 0.34 million). This saved 26% on the real data and 58% on the scaled copy, but the scaled query still took 20.5 seconds.

**Why the rewrites are not enough at scale:** both queries must still add up all 3.6 million cost rows, which takes about 12 seconds in the plan (`GroupAggregate … rows=604943 loops=3`). An index cannot avoid reading data that the answer depends on.

### Q2b and Q8b: Materialised view

`mv_accident_totals` stores each accident's total cost, fatalities and injuries, calculated once. It has an index on `total_cost_usd DESC`.

- **Q8b** reads the first 10 entries of that index (4 pages), then looks up those 10 accidents by primary key. The whole query reads 85 pages and takes **0.35 ms instead of 49,370 ms**.
- **Q2b** sums 605,200 stored totals instead of 3.6 million cost rows, taking **609 ms instead of 20,630 ms**.

```
Limit  (actual time=0.018..0.027 rows=10.00 loops=1)
  ->  Index Scan using mv_accident_totals_cost on mv_accident_totals  (actual time=0.017..0.024 rows=10.00 loops=1)
        Buffers: shared hit=4
```

## 5. The Cost of Optimisation

Every optimisation trades something for read speed.

### Storage (scaled copy)

| Object | Size |
|---|---|
| `accident` table data (81,354 pages of 8 KB, as read by the Q4 full scan) | about 636 MB |
| `accident` table including all its indexes | 1,034 MB |
| Trigram index on narrative | **322 MB** (about half the size of the table data) |
| Materialised view and its two indexes | 71 MB |
| Each B-tree index | about 4 MB (4.0–4.4 MB) |

The B-tree indexes are unusually small because each value appears 100 times in the scaled copy, and PostgreSQL 13+ stores repeated index values only once (deduplication). With 605,200 genuinely different accidents they would be larger.

### Write speed (`sql/04_write_cost.sql`, `results/write_cost_run.txt`)

Inserting 6,052 new accidents into the scaled copy (one run; each test is rolled back):

| Indexes present | Insert time |
|---|---|
| None of the new indexes | 739 ms |
| Five new B-tree indexes | 1,189 ms |
| Five B-tree + trigram index | **32,471 ms** |

The five B-tree indexes make inserts about 1.6 times slower, which is acceptable. The trigram index makes inserts **about 27 times slower than with the B-trees alone**, because every narrative of about 950 characters generates hundreds of trigram entries.

### Freshness

The materialised view is a snapshot. New reports do not appear in it until it is refreshed:

| Dataset | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (median of 3) |
|---|---|
| Real (6,052 accidents) | 329 ms |
| Scaled (605,200 accidents) | 35,272 ms |

`CONCURRENTLY` lets users keep reading the old snapshot while it refreshes. It requires the unique index `mv_accident_totals_pk`.

### Is each trade-off worth it for PipeSafe?

| Optimisation | Decision | Reason |
|---|---|---|
| `idx_accident_operator_date`, `idx_accident_datetime`, `idx_accident_cause_detail` | **Keep** | Large read gains for searches (Q3, Q4, Q7) at a small write cost |
| Trigram index | **Keep** | Accident reports arrive a few hundred per year (about 6,000 in 16 years), so slower inserts do not matter. Narrative search is used constantly by analysts and investigators. |
| `idx_accident_county`, `idx_accident_commodity` | **Drop** | Neither was used by any of the eight queries (checked in every saved plan), so they only add write cost and storage. They would be worth re-adding if counties or commodity subtypes were ever deleted often, because PostgreSQL then checks `accident` for rows still referencing them. |
| Rewritten summary view | **Keep** | Never slower: 1.4× faster on real data and 2.4× on the scaled copy, same results |
| Materialised view | **Keep, refreshed nightly** (or after each batch of reports) | Dashboards and "top 10" reports become instant. Data up to a day old is acceptable for trend reports. Live search queries still use the normal tables. |

## 6. Conclusions

1. **Missing foreign-key indexes are a common avoidable cost, but only where queries filter or join selectively on them.** PostgreSQL does not create them automatically. The right ones, plus one composite index matched to the filter and sort, gave 5–46× gains on searches at scale. Two of the six new indexes were never used, which is why each index should be checked against real plans before it is kept.
2. **Indexes only help selective queries.** Q1 and Q5 read every row, so no index can help, and the planner rightly ignored them.
3. **Specialised index types solve problems B-trees cannot.** The trigram index made substring search 49–104× faster, at a real cost in storage and write speed.
4. **For totals over millions of rows, pre-calculation beats indexing.** A materialised view made the "ten costliest accidents" report about 140,000× faster (49 seconds to 0.35 ms), at the cost of a scheduled refresh.
5. **Small data hides problems.** On 6,052 rows every query took under 200 ms before optimisation. Only the scaled copy showed which designs would not survive growth.

## 7. How to Reproduce

From this folder, with the Portfolio 1 database loaded:

```bash
psql -d pipesafe -f sql/01_setup_bench.sql      # build the scaled copy (a few minutes)
python scripts/benchmark.py "dbname=pipesafe"   # before/after timings for both datasets
psql -d pipesafe -f sql/04_write_cost.sql       # write-cost test
```

`benchmark.py` applies `sql/03_undo.sql` (baseline) and `sql/02_optimise.sql` (optimised) itself. It writes `results/timings.csv` and one plan file per query, schema and phase.
