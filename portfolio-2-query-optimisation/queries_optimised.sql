-- =====================================================================
-- MIT 8103 Portfolio 2 - Query Processing and Optimisation
-- queries_optimised.sql : same eight queries after optimisation.
-- Only Q2 is rewritten. The others are unchanged: they benefit from the
-- indexes in sql/02_optimise.sql, and Q8 from the rewritten view.
-- The extra queries Q2b and Q8b answer the same questions from the
-- materialised view mv_accident_totals (pre-calculated totals, see sql/02_optimise.sql).
-- Each query answers one of the key operations in the case study.
-- Run with:  SET search_path TO pipesafe;   (or bench, for the scaled copy)
-- =====================================================================

-- Q1. Accidents, barrels released and total cost per year by cause category
--     (case study operation 6: trend reports)
SELECT EXTRACT(YEAR FROM a.accident_datetime)::INT AS accident_year,
       cc.category_name                          AS cause_category,
       COUNT(*)                                  AS accidents,
       ROUND(SUM(a.unintentional_release_bbls))  AS bbl_released
FROM accident a
JOIN cause_detail   cd ON cd.cause_detail_id   = a.cause_detail_id
JOIN cause_category cc ON cc.cause_category_id = cd.cause_category_id
GROUP BY 1, 2
ORDER BY 1, 3 DESC;

-- Q2 (rewritten). Total each accident's costs first, then join.
--     Removes COUNT(DISTINCT ...), which forced a large sort.
WITH accident_totals AS (
    SELECT report_number, SUM(amount_usd) AS cost_usd
    FROM accident_cost
    GROUP BY report_number
)
SELECT o.operator_id, o.operator_name,
       COUNT(*)        AS accidents,
       SUM(t.cost_usd) AS total_cost_usd
FROM accident_totals t
JOIN accident a ON a.report_number = t.report_number
JOIN operator o ON o.operator_id   = a.operator_id
GROUP BY o.operator_id, o.operator_name
ORDER BY total_cost_usd DESC
LIMIT 10;

-- Q3. Texas accidents in 2023, newest first
--     (operation 4: search by state and date range)
SELECT a.report_number, a.accident_datetime, co.county_name,
       a.unintentional_release_bbls, a.recovered_bbls
FROM accident a
JOIN county co ON co.county_id = a.county_id
WHERE co.state_code = 'TX'
  AND a.accident_datetime >= '2023-01-01'
  AND a.accident_datetime <  '2024-01-01'
ORDER BY a.accident_datetime DESC;

-- Q4. Full accident history of one operator (Phillips 66 Pipeline, ID 31684)
--     (operation 4: search by operator; compliance audits)
SELECT a.report_number, a.accident_datetime, a.report_type,
       a.unintentional_release_bbls, a.recovered_bbls
FROM accident a
WHERE a.operator_id = 31684
ORDER BY a.accident_datetime DESC;

-- Q5. Recovery rate by commodity type
--     (operation 5: impact metrics)
SELECT ct.type_name                                         AS commodity_type,
       COUNT(*)                                             AS accidents,
       ROUND(SUM(a.unintentional_release_bbls))             AS bbl_released,
       ROUND(SUM(a.recovered_bbls))                         AS bbl_recovered,
       ROUND(100.0 * SUM(a.recovered_bbls)
             / NULLIF(SUM(a.unintentional_release_bbls), 0), 1) AS recovery_pct
FROM accident a
JOIN commodity_subtype cs ON cs.commodity_subtype_id = a.commodity_subtype_id
JOIN commodity_type    ct ON ct.commodity_type_id    = cs.commodity_type_id
GROUP BY ct.type_name
ORDER BY bbl_released DESC;

-- Q6. Accidents whose narrative mentions frozen equipment
--     (operation 4: free-text search of investigation narratives)
SELECT a.report_number, a.accident_datetime, LEFT(a.narrative, 80) AS narrative_start
FROM accident a
WHERE a.narrative ILIKE '%frozen%'
ORDER BY a.accident_datetime DESC;

-- Q7. External corrosion accidents where the pipe was NOT under cathodic
--     protection, by state (operation 3/6: cause analysis)
SELECT s.state_code, COUNT(*) AS accidents
FROM corrosion_detail d
JOIN accident       a  ON a.report_number   = d.report_number
JOIN cause_detail   cd ON cd.cause_detail_id = a.cause_detail_id
JOIN county         co ON co.county_id       = a.county_id
JOIN state          s  ON s.state_code       = co.state_code
WHERE cd.detail_name = 'EXTERNAL CORROSION'
  AND d.under_cathodic_protection = FALSE
GROUP BY s.state_code
ORDER BY accidents DESC;

-- Q8. Ten most costly accidents, from the summary view
--     (operation 6: most costly incidents)
SELECT report_number, accident_year, operator_name, cause_category,
       total_cost_usd, total_fatalities, total_injuries
FROM v_accident_summary
ORDER BY total_cost_usd DESC, report_number
LIMIT 10;

-- Q2b. Same as Q2, using the materialised view of per-accident totals
SELECT o.operator_id, o.operator_name,
       COUNT(*)              AS accidents,
       SUM(m.total_cost_usd) AS total_cost_usd
FROM mv_accident_totals m
JOIN operator o ON o.operator_id = m.operator_id
GROUP BY o.operator_id, o.operator_name
ORDER BY total_cost_usd DESC
LIMIT 10;

-- Q8b. Same as Q8: take the ten largest totals from the materialised view
--      (using its index), then look up details for only those ten accidents
SELECT m.report_number,
       EXTRACT(YEAR FROM a.accident_datetime)::INT AS accident_year,
       o.operator_name,
       cc.category_name                            AS cause_category,
       m.total_cost_usd, m.total_fatalities, m.total_injuries
FROM (SELECT * FROM mv_accident_totals
      ORDER BY total_cost_usd DESC, report_number
      LIMIT 10) m
JOIN accident       a  ON a.report_number      = m.report_number
JOIN operator       o  ON o.operator_id        = a.operator_id
JOIN cause_detail   cd ON cd.cause_detail_id   = a.cause_detail_id
JOIN cause_category cc ON cc.cause_category_id = cd.cause_category_id
ORDER BY m.total_cost_usd DESC, m.report_number;
