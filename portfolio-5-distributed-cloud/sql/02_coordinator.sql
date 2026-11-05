-- =====================================================================
-- 02_coordinator.sql : run on the PRIMARY (port 5601), database pipesafe
-- Builds a table that is split ("sharded") by region across two servers:
--   SOUTH          -> shard_a (port 5603)
--   every other    -> shard_b (port 5604)
-- Applications query ONE table; PostgreSQL routes each row and each query
-- to the right server using postgres_fdw (foreign data wrapper).
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
DROP SCHEMA IF EXISTS dist CASCADE;
CREATE SCHEMA dist;

DROP SERVER IF EXISTS shard_a CASCADE;
DROP SERVER IF EXISTS shard_b CASCADE;
CREATE SERVER shard_a FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '/tmp', port '5603', dbname 'pipesafe_shard', async_capable 'true');
CREATE SERVER shard_b FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '/tmp', port '5604', dbname 'pipesafe_shard', async_capable 'true');
CREATE USER MAPPING FOR CURRENT_USER SERVER shard_a OPTIONS (user 'postgres');
CREATE USER MAPPING FOR CURRENT_USER SERVER shard_b OPTIONS (user 'postgres');

-- The distributed table: partitioned by region, each partition on another server
CREATE TABLE dist.accident_by_region (
    report_number               BIGINT        NOT NULL,
    region                      VARCHAR(20)   NOT NULL,
    state_code                  CHAR(2),
    accident_datetime           TIMESTAMP     NOT NULL,
    operator_id                 INTEGER       NOT NULL,
    cause_category              VARCHAR(60)   NOT NULL,
    unintentional_release_bbls  NUMERIC(12,2) NOT NULL,
    recovered_bbls              NUMERIC(12,2) NOT NULL,
    total_cost_usd              NUMERIC(14,2) NOT NULL
) PARTITION BY LIST (region);

CREATE FOREIGN TABLE dist.accident_south
    PARTITION OF dist.accident_by_region FOR VALUES IN ('SOUTH')
    SERVER shard_a OPTIONS (schema_name 'public', table_name 'accident_shard');
CREATE FOREIGN TABLE dist.accident_other
    PARTITION OF dist.accident_by_region DEFAULT
    SERVER shard_b OPTIONS (schema_name 'public', table_name 'accident_shard');

-- Load: region comes from the onshore county's state, or for offshore
-- accidents from the adjacent state; 'UNKNOWN' where neither is recorded.
INSERT INTO dist.accident_by_region
SELECT a.report_number,
       COALESCE(s.region, s2.region, 'UNKNOWN'),
       COALESCE(s.state_code, s2.state_code),
       a.accident_datetime,
       a.operator_id,
       v.cause_category,
       a.unintentional_release_bbls,
       a.recovered_bbls,
       v.total_cost_usd
FROM pipesafe.accident a
JOIN pipesafe.v_accident_summary v ON v.report_number = a.report_number
LEFT JOIN pipesafe.county c             ON c.county_id      = a.county_id
LEFT JOIN pipesafe.state s              ON s.state_code     = c.state_code
LEFT JOIN pipesafe.offshore_location o  ON o.report_number  = a.report_number
LEFT JOIN pipesafe.state s2             ON s2.state_code    = o.adjacent_state_code;
