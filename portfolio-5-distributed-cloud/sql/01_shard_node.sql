-- =====================================================================
-- 01_shard_node.sql : run on EACH shard server (ports 5603 and 5604)
--   psql -p 5603 -d pipesafe_shard -f sql/01_shard_node.sql
--   psql -p 5604 -d pipesafe_shard -f sql/01_shard_node.sql
-- Each shard holds the accidents for its regions only. The coordinator
-- decides which shard a row goes to.
-- =====================================================================
DROP TABLE IF EXISTS accident_shard;
CREATE TABLE accident_shard (
    report_number               BIGINT        PRIMARY KEY,
    region                      VARCHAR(20)   NOT NULL,
    state_code                  CHAR(2),
    accident_datetime           TIMESTAMP     NOT NULL,
    operator_id                 INTEGER       NOT NULL,
    cause_category              VARCHAR(60)   NOT NULL,
    unintentional_release_bbls  NUMERIC(12,2) NOT NULL CHECK (unintentional_release_bbls >= 0),
    recovered_bbls              NUMERIC(12,2) NOT NULL CHECK (recovered_bbls >= 0),
    total_cost_usd              NUMERIC(14,2) NOT NULL CHECK (total_cost_usd >= 0)
);
CREATE INDEX ON accident_shard (state_code, accident_datetime);
