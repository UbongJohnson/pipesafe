-- =====================================================================
-- 02_optimise.sql : indexes and query rewrites
-- Applies to whichever schema is first in search_path (pipesafe or bench).
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public;

-- PostgreSQL indexes primary keys automatically, but NOT foreign keys.
-- None of the accident table's foreign-key columns had an index.

-- Q4: one operator's history, newest first. Composite index matches both
-- the filter (operator_id) and the sort (accident_datetime DESC).
CREATE INDEX IF NOT EXISTS idx_accident_operator_date
    ON accident (operator_id, accident_datetime DESC);

-- Q3: date-range search.
CREATE INDEX IF NOT EXISTS idx_accident_datetime
    ON accident (accident_datetime);

-- Q3 / Q7: joins from accident to county (foreign key).
CREATE INDEX IF NOT EXISTS idx_accident_county
    ON accident (county_id);

-- Q7: join from accident to cause_detail (foreign key).
CREATE INDEX IF NOT EXISTS idx_accident_cause_detail
    ON accident (cause_detail_id);

-- Q5: join from accident to commodity_subtype (foreign key).
CREATE INDEX IF NOT EXISTS idx_accident_commodity
    ON accident (commodity_subtype_id);

-- Q6: ILIKE '%word%' cannot use a normal B-tree index because the pattern
-- starts with a wildcard. A trigram GIN index can.
CREATE INDEX IF NOT EXISTS idx_accident_narrative_trgm
    ON accident USING gin (narrative public.gin_trgm_ops);

-- Q8: rewrite the summary view. The original runs three correlated
-- subqueries for every accident row. The new version aggregates costs and
-- casualties once each and joins the results.
CREATE OR REPLACE VIEW v_accident_summary AS
WITH cost_totals AS (
    SELECT report_number, SUM(amount_usd) AS total_cost_usd
    FROM accident_cost GROUP BY report_number
),
casualty_totals AS (
    SELECT report_number, SUM(fatalities) AS total_fatalities, SUM(injuries) AS total_injuries
    FROM casualty GROUP BY report_number
)
SELECT a.report_number,
       EXTRACT(YEAR FROM a.accident_datetime)::INT AS accident_year,
       a.accident_datetime,
       o.operator_name,
       cc.category_name                            AS cause_category,
       cd.detail_name                              AS cause_detail,
       ct.type_name                                AS commodity_type,
       a.unintentional_release_bbls,
       a.recovered_bbls,
       COALESCE(k.total_cost_usd, 0)               AS total_cost_usd,
       COALESCE(x.total_fatalities, 0)             AS total_fatalities,
       COALESCE(x.total_injuries, 0)               AS total_injuries
FROM accident a
JOIN operator          o  ON o.operator_id           = a.operator_id
JOIN cause_detail      cd ON cd.cause_detail_id      = a.cause_detail_id
JOIN cause_category    cc ON cc.cause_category_id    = cd.cause_category_id
JOIN commodity_subtype cs ON cs.commodity_subtype_id = a.commodity_subtype_id
JOIN commodity_type    ct ON ct.commodity_type_id    = cs.commodity_type_id
LEFT JOIN cost_totals     k ON k.report_number = a.report_number
LEFT JOIN casualty_totals x ON x.report_number = a.report_number;

-- Q2b / Q8b: totals that need every cost row (3.6 million rows in the
-- scaled copy) cannot be sped up by an index. A materialised view
-- calculates them once and stores the result. It must be refreshed after
-- new reports arrive:  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_accident_totals;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_accident_totals AS
SELECT a.report_number,
       a.operator_id,
       COALESCE(k.total_cost_usd, 0)   AS total_cost_usd,
       COALESCE(x.total_fatalities, 0) AS total_fatalities,
       COALESCE(x.total_injuries, 0)   AS total_injuries
FROM accident a
LEFT JOIN (SELECT report_number, SUM(amount_usd) AS total_cost_usd
           FROM accident_cost GROUP BY report_number) k ON k.report_number = a.report_number
LEFT JOIN (SELECT report_number, SUM(fatalities) AS total_fatalities, SUM(injuries) AS total_injuries
           FROM casualty GROUP BY report_number) x ON x.report_number = a.report_number;

-- A unique index is required for REFRESH ... CONCURRENTLY (readers are not blocked)
CREATE UNIQUE INDEX IF NOT EXISTS mv_accident_totals_pk
    ON mv_accident_totals (report_number);
CREATE INDEX IF NOT EXISTS mv_accident_totals_cost
    ON mv_accident_totals (total_cost_usd DESC, report_number);

-- Refresh planner statistics so the new indexes are costed correctly.
ANALYZE;
