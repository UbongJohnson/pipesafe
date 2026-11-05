-- =====================================================================
-- MIT 8103 Portfolio 2 - Query Processing and Optimisation
-- queries.sql : eight business queries for PipeSafe Analytics
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

-- Q2. Ten operators with the highest total accident cost
--     (operation 6: operators with the most costly accidents)
SELECT o.operator_id, o.operator_name,
       COUNT(DISTINCT a.report_number) AS accidents,
       SUM(c.amount_usd)               AS total_cost_usd
FROM accident_cost c
JOIN accident a ON a.report_number = c.report_number
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
