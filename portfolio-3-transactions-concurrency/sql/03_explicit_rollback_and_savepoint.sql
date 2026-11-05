-- =====================================================================
-- 03_explicit_rollback_and_savepoint.sql
-- A. ROLLBACK undoes a mistake before anyone else sees it.
-- B. SAVEPOINT undoes only part of a transaction.
-- Run after 00_setup_test_data.sql.
-- =====================================================================
SET search_path TO pipesafe;
\set ON_ERROR_STOP off

\echo '=== A. Explicit ROLLBACK ==='
\echo '--- open reports before:'
SELECT report_type, COUNT(*) FROM accident
WHERE report_type IN ('ORIGINAL', 'SUPPLEMENTAL') GROUP BY report_type ORDER BY 1;

BEGIN;
-- Mistake: the WHERE clause should have named ONE report, but it closes every open ORIGINAL report
UPDATE accident SET report_type = 'ORIGINAL FINAL' WHERE report_type = 'ORIGINAL';
\echo '--- inside the transaction, open ORIGINAL reports left:'
SELECT COUNT(*) AS open_original FROM accident WHERE report_type = 'ORIGINAL';
ROLLBACK;

\echo '--- after ROLLBACK, nothing has changed:'
SELECT report_type, COUNT(*) FROM accident
WHERE report_type IN ('ORIGINAL', 'SUPPLEMENTAL') GROUP BY report_type ORDER BY 1;

\echo '=== B. SAVEPOINT: keep the good work, undo only the failed step ==='
BEGIN;
UPDATE accident SET recovered_bbls = 320 WHERE report_number = 99990002;    -- good update
SAVEPOINT before_casualty;
INSERT INTO casualty (report_number, person_group, fatalities, injuries)
VALUES (99990002, 'VISITOR', 0, 1);                                        -- invalid group
ROLLBACK TO SAVEPOINT before_casualty;                                     -- undo only the insert
INSERT INTO casualty (report_number, person_group, fatalities, injuries)
VALUES (99990002, 'PUBLIC', 0, 1);                                         -- corrected insert
COMMIT;

\echo '--- result: the update before the savepoint and the corrected insert were both kept'
SELECT a.report_number, a.recovered_bbls, c.person_group, c.injuries
FROM accident a LEFT JOIN casualty c USING (report_number)
WHERE a.report_number = 99990002;
