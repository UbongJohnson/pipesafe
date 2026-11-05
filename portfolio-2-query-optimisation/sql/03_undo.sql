-- 03_undo.sql : remove the optimisations to return to the baseline
DROP INDEX IF EXISTS idx_accident_operator_date;
DROP INDEX IF EXISTS idx_accident_datetime;
DROP INDEX IF EXISTS idx_accident_county;
DROP INDEX IF EXISTS idx_accident_cause_detail;
DROP INDEX IF EXISTS idx_accident_commodity;
DROP INDEX IF EXISTS idx_accident_narrative_trgm;
DROP MATERIALIZED VIEW IF EXISTS mv_accident_totals;

-- Original view from Portfolio 1 (correlated subqueries)
CREATE OR REPLACE VIEW v_accident_summary AS
SELECT a.report_number,
       EXTRACT(YEAR FROM a.accident_datetime)::INT AS accident_year,
       a.accident_datetime,
       o.operator_name,
       cc.category_name AS cause_category,
       cd.detail_name   AS cause_detail,
       ct.type_name     AS commodity_type,
       a.unintentional_release_bbls,
       a.recovered_bbls,
       COALESCE((SELECT SUM(c.amount_usd) FROM accident_cost c WHERE c.report_number = a.report_number), 0) AS total_cost_usd,
       COALESCE((SELECT SUM(x.fatalities) FROM casualty x      WHERE x.report_number = a.report_number), 0) AS total_fatalities,
       COALESCE((SELECT SUM(x.injuries)   FROM casualty x      WHERE x.report_number = a.report_number), 0) AS total_injuries
FROM accident a
JOIN operator          o  ON o.operator_id           = a.operator_id
JOIN cause_detail      cd ON cd.cause_detail_id      = a.cause_detail_id
JOIN cause_category    cc ON cc.cause_category_id    = cd.cause_category_id
JOIN commodity_subtype cs ON cs.commodity_subtype_id = a.commodity_subtype_id
JOIN commodity_type    ct ON ct.commodity_type_id    = cs.commodity_type_id;
ANALYZE;
