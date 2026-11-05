-- =====================================================================
-- 03_sharding_queries.sql : run on the primary/coordinator (port 5601)
-- =====================================================================
\echo '=== 1. Rows per shard (data distribution) ==='
SELECT 'shard_a (SOUTH)' AS shard, COUNT(*) AS accidents FROM dist.accident_south
UNION ALL
SELECT 'shard_b (all other regions)', COUNT(*) FROM dist.accident_other;

\echo '=== 2. Same total as the unsharded database? (expect 6052 / 4619299360.00) ==='
SELECT COUNT(*) AS accidents, SUM(total_cost_usd) AS total_cost_usd FROM dist.accident_by_region;

\echo '=== 3. Single-shard query: Texas accidents in 2023 (partition pruning) ==='
EXPLAIN (VERBOSE, COSTS OFF)
SELECT report_number, accident_datetime, unintentional_release_bbls
FROM dist.accident_by_region
WHERE region = 'SOUTH' AND state_code = 'TX'
  AND accident_datetime >= '2023-01-01' AND accident_datetime < '2024-01-01';

SELECT COUNT(*) AS tx_2023_accidents
FROM dist.accident_by_region
WHERE region = 'SOUTH' AND state_code = 'TX'
  AND accident_datetime >= '2023-01-01' AND accident_datetime < '2024-01-01';

\echo '=== 4a. Cross-shard query: cost by cause category (scatter-gather) ==='
\echo '    Default: every shard sends ALL its rows; the coordinator does the grouping.'
SET enable_partitionwise_aggregate = off;
EXPLAIN (VERBOSE, COSTS OFF)
SELECT cause_category, COUNT(*), SUM(total_cost_usd)
FROM dist.accident_by_region GROUP BY cause_category;

\echo '=== 4b. Grouping that includes the shard key, with partition-wise aggregation ==='
\echo '    Each shard does its own GROUP BY and sends back only its totals.'
\echo '    (PostgreSQL 16 only pushes a GROUP BY to the shards when it includes'
\echo '     the partition key, here region.)'
SET enable_partitionwise_aggregate = on;
EXPLAIN (VERBOSE, COSTS OFF)
SELECT region, cause_category, COUNT(*), SUM(total_cost_usd)
FROM dist.accident_by_region GROUP BY region, cause_category;

SELECT cause_category, COUNT(*) AS accidents, SUM(total_cost_usd) AS total_cost_usd
FROM dist.accident_by_region GROUP BY cause_category ORDER BY total_cost_usd DESC;
RESET enable_partitionwise_aggregate;

\echo '=== 5. Routing on insert: a new Louisiana report goes to shard_a ==='
INSERT INTO dist.accident_by_region VALUES
    (99995100, 'SOUTH', 'LA', '2026-10-30 07:45', 31684, 'CORROSION FAILURE', 12, 10, 25000);
SELECT 'shard_a' AS shard, COUNT(*) FROM dist.accident_south WHERE report_number = 99995100
UNION ALL
SELECT 'shard_b', COUNT(*) FROM dist.accident_other WHERE report_number = 99995100;
DELETE FROM dist.accident_by_region WHERE report_number = 99995100;

\echo '=== 6. Skew check: region sharding vs hash sharding on report_number ==='
SELECT 'by region' AS strategy,
       SUM(CASE WHEN region = 'SOUTH' THEN 1 ELSE 0 END) AS shard_a,
       SUM(CASE WHEN region <> 'SOUTH' THEN 1 ELSE 0 END) AS shard_b
FROM dist.accident_by_region
UNION ALL
SELECT 'by hash(report_number)',
       SUM(CASE WHEN abs(hashint8(report_number)) % 2 = 0 THEN 1 ELSE 0 END),
       SUM(CASE WHEN abs(hashint8(report_number)) % 2 = 1 THEN 1 ELSE 0 END)
FROM dist.accident_by_region;
