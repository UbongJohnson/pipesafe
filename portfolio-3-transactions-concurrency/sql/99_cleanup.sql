-- 99_cleanup.sql : remove all Portfolio 3 test reports (child rows cascade)
SET search_path TO pipesafe;
DELETE FROM accident WHERE report_number BETWEEN 99990000 AND 99999999;
SELECT COUNT(*) AS accidents_after_cleanup FROM accident;   -- should be 6,052
