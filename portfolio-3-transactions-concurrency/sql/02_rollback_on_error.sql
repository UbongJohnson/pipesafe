-- =====================================================================
-- 02_rollback_on_error.sql : atomicity - a failure undoes EVERYTHING
-- The accident row is inserted successfully, but a later statement breaks
-- a CHECK constraint. PostgreSQL aborts the transaction and the accident
-- row disappears too. Run after 00_setup_test_data.sql.
-- =====================================================================
SET search_path TO pipesafe;
\set ON_ERROR_STOP off

\echo '=== Example A: negative cost breaks CHECK (amount_usd >= 0) ==='
BEGIN;
INSERT INTO accident (report_number, report_type, report_received_date, operator_id,
    on_off_shore, latitude, longitude, accident_datetime, pipe_facility_type,
    system_part_id, item_involved_id, commodity_subtype_id, release_type,
    unintentional_release_bbls, recovered_bbls, cause_detail_id, narrative)
VALUES (99990011, 'ORIGINAL', DATE '2026-10-26', 31684, 'ONSHORE', 29.97, -90.42,
    TIMESTAMP '2026-10-25 08:00', 'INTRASTATE', 1, 1,
    (SELECT s.commodity_subtype_id FROM commodity_subtype s JOIN commodity_type t USING (commodity_type_id)
      WHERE t.type_name = 'CRUDE OIL' AND s.subtype_name = 'NOT SPECIFIED'),
    'LEAK', 40, 10, 1, 'TEST REPORT - Portfolio 3 rollback demo');
\echo '--- accident row inserted inside the transaction:'
SELECT report_number, unintentional_release_bbls FROM accident WHERE report_number = 99990011;

INSERT INTO accident_cost (report_number, cost_type_id, amount_usd)
VALUES (99990011, 4, -5000);          -- invalid: negative cost

\echo '--- any further statement is refused while the transaction is aborted:'
INSERT INTO casualty (report_number, person_group, fatalities, injuries)
VALUES (99990011, 'EMPLOYEE', 0, 1);
COMMIT;                               -- PostgreSQL turns this into ROLLBACK

\echo '--- after the transaction: the accident row is gone too'
SELECT COUNT(*) AS rows_for_99990011 FROM accident WHERE report_number = 99990011;

\echo '=== Example B: business rule - cannot recover more oil than was released ==='
BEGIN;
UPDATE accident SET recovered_bbls = 650 WHERE report_number = 99990001;   -- released is 500
ROLLBACK;
SELECT report_number, unintentional_release_bbls, recovered_bbls
FROM accident WHERE report_number = 99990001;
