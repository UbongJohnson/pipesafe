-- =====================================================================
-- 00_setup_test_data.sql : test reports for the Portfolio 3 demos
-- Report numbers starting 9999 are not real PHMSA reports (real ones are
-- YEAR + sequence, e.g. 20260244). Real data is never changed: every demo
-- either uses these test reports or rolls back.
-- =====================================================================
SET search_path TO pipesafe;
DELETE FROM accident WHERE report_number BETWEEN 99990000 AND 99999999;

-- Two OPEN reports (report_type 'ORIGINAL') that investigators are still
-- updating: 500 barrels released, 300 recovered so far.
INSERT INTO accident (report_number, report_type, report_received_date, operator_id,
    on_off_shore, county_id, latitude, longitude, accident_datetime, pipe_facility_type,
    system_part_id, item_involved_id, commodity_subtype_id, release_type,
    unintentional_release_bbls, recovered_bbls, cause_detail_id, narrative)
SELECT r.report_number, 'ORIGINAL', DATE '2026-10-20', 31684,
       'ONSHORE',
       (SELECT county_id FROM county WHERE state_code = 'LA' AND county_name = 'ST CHARLES'),
       29.95, -90.40, TIMESTAMP '2026-10-18 09:30', 'INTRASTATE',
       (SELECT system_part_id FROM system_part WHERE part_name = 'ONSHORE PIPELINE, INCLUDING VALVE SITES'),
       (SELECT item_involved_id FROM item_involved WHERE item_name = 'PIPE'),
       (SELECT s.commodity_subtype_id FROM commodity_subtype s JOIN commodity_type t USING (commodity_type_id)
         WHERE t.type_name = 'CRUDE OIL' AND s.subtype_name = 'NOT SPECIFIED'),
       'LEAK', 500, 300,
       (SELECT cause_detail_id FROM cause_detail WHERE detail_name = 'EXTERNAL CORROSION'),
       'TEST REPORT - Portfolio 3 transaction demo'
FROM (VALUES (99990001), (99990002)) AS r(report_number);

SELECT report_number, report_type, unintentional_release_bbls, recovered_bbls
FROM accident WHERE report_number BETWEEN 99990000 AND 99999999 ORDER BY 1;
