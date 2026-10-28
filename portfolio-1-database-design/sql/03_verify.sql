-- 03_verify.sql : checks that the load is complete and matches the source file
SET search_path TO pipesafe;

-- 1. Row counts per table
SELECT 'operator' AS table_name, COUNT(*) FROM operator UNION ALL
SELECT 'operator_name_history', COUNT(*) FROM operator_name_history UNION ALL
SELECT 'facility', COUNT(*) FROM facility UNION ALL
SELECT 'state', COUNT(*) FROM state UNION ALL
SELECT 'county', COUNT(*) FROM county UNION ALL
SELECT 'commodity_type', COUNT(*) FROM commodity_type UNION ALL
SELECT 'commodity_subtype', COUNT(*) FROM commodity_subtype UNION ALL
SELECT 'cause_category', COUNT(*) FROM cause_category UNION ALL
SELECT 'cause_detail', COUNT(*) FROM cause_detail UNION ALL
SELECT 'system_part', COUNT(*) FROM system_part UNION ALL
SELECT 'item_involved', COUNT(*) FROM item_involved UNION ALL
SELECT 'detection_method', COUNT(*) FROM detection_method UNION ALL
SELECT 'cost_type', COUNT(*) FROM cost_type UNION ALL
SELECT 'accident', COUNT(*) FROM accident UNION ALL
SELECT 'offshore_location', COUNT(*) FROM offshore_location UNION ALL
SELECT 'casualty', COUNT(*) FROM casualty UNION ALL
SELECT 'accident_cost', COUNT(*) FROM accident_cost UNION ALL
SELECT 'corrosion_detail', COUNT(*) FROM corrosion_detail UNION ALL
SELECT 'excavation_detail', COUNT(*) FROM excavation_detail UNION ALL
SELECT 'incorrect_operation_detail', COUNT(*) FROM incorrect_operation_detail;

-- 2. Totals should equal the raw file:
--    6,052 accidents | 1,388,888 bbl released | 552,028 bbl recovered
--    $4,619,299,360 total cost | 16 fatalities | 46 injuries
SELECT COUNT(*)                                  AS accidents,
       ROUND(SUM(unintentional_release_bbls))   AS bbl_released,
       ROUND(SUM(recovered_bbls))               AS bbl_recovered,
       SUM(total_cost_usd)                       AS total_cost_usd,
       SUM(total_fatalities)                     AS fatalities,
       SUM(total_injuries)                       AS injuries
FROM v_accident_summary;

-- 3. Accidents per cause category (should match the dataset analysis)
SELECT cause_category, COUNT(*) AS accidents
FROM v_accident_summary GROUP BY cause_category ORDER BY accidents DESC;

-- 4. Each cause-detail table only holds accidents of its own cause
SELECT 'corrosion' AS detail_table, COUNT(*) AS wrong_cause
FROM corrosion_detail d JOIN v_accident_summary v USING (report_number)
WHERE v.cause_category <> 'CORROSION FAILURE'
UNION ALL
SELECT 'excavation', COUNT(*)
FROM excavation_detail d JOIN v_accident_summary v USING (report_number)
WHERE v.cause_category <> 'EXCAVATION DAMAGE'
UNION ALL
SELECT 'incorrect_operation', COUNT(*)
FROM incorrect_operation_detail d JOIN v_accident_summary v USING (report_number)
WHERE v.cause_category <> 'INCORRECT OPERATION';

-- 5. Operators that have reported under more than one name
SELECT o.operator_id, o.operator_name AS current_name,
       STRING_AGG(h.operator_name, ' | ' ORDER BY h.first_report_date) AS all_names
FROM operator o JOIN operator_name_history h USING (operator_id)
GROUP BY o.operator_id, o.operator_name
HAVING COUNT(*) > 1
ORDER BY o.operator_id
LIMIT 5;
