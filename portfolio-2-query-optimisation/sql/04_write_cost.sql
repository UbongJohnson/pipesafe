-- =====================================================================
-- 04_write_cost.sql : what the indexes cost when new reports are added
-- Inserts 6,052 new accidents into the scaled copy (bench) three ways.
-- Every test is inside a transaction that is rolled back, so the data
-- and the indexes are left unchanged. Run after 02_optimise.sql.
--   psql -d pipesafe -f sql/04_write_cost.sql
-- =====================================================================
\timing on
SET search_path TO bench, public;

\echo '--- A. With all six new indexes ---'
BEGIN;
INSERT INTO accident SELECT report_number * 1000 + 1, report_type, report_received_date, operator_id, facility_id, segment_name, on_off_shore, county_id, city_name, latitude, longitude, accident_datetime, time_zone, pipe_facility_type, system_part_id, item_involved_id, installation_year, detection_method_id, commodity_subtype_id, release_type, unintentional_release_bbls, intentional_release_bbls, recovered_bbls, ignited, exploded, shutdown_required, public_evacuated, cause_detail_id, narrative FROM pipesafe.accident;
ROLLBACK;

\echo '--- B. Without the trigram (text search) index ---'
BEGIN;
DROP INDEX idx_accident_narrative_trgm;
INSERT INTO accident SELECT report_number * 1000 + 2, report_type, report_received_date, operator_id, facility_id, segment_name, on_off_shore, county_id, city_name, latitude, longitude, accident_datetime, time_zone, pipe_facility_type, system_part_id, item_involved_id, installation_year, detection_method_id, commodity_subtype_id, release_type, unintentional_release_bbls, intentional_release_bbls, recovered_bbls, ignited, exploded, shutdown_required, public_evacuated, cause_detail_id, narrative FROM pipesafe.accident;
ROLLBACK;

\echo '--- C. Without any of the six new indexes ---'
BEGIN;
DROP INDEX idx_accident_operator_date, idx_accident_datetime, idx_accident_county,
           idx_accident_cause_detail, idx_accident_commodity, idx_accident_narrative_trgm;
INSERT INTO accident SELECT report_number * 1000 + 3, report_type, report_received_date, operator_id, facility_id, segment_name, on_off_shore, county_id, city_name, latitude, longitude, accident_datetime, time_zone, pipe_facility_type, system_part_id, item_involved_id, installation_year, detection_method_id, commodity_subtype_id, release_type, unintentional_release_bbls, intentional_release_bbls, recovered_bbls, ignited, exploded, shutdown_required, public_evacuated, cause_detail_id, narrative FROM pipesafe.accident;
ROLLBACK;
