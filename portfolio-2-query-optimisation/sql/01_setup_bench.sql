-- =====================================================================
-- 01_setup_bench.sql : builds a SCALED-UP TEST COPY called "bench"
--
-- The real database has 6,052 accidents, small enough that PostgreSQL
-- often reads whole tables instead of using indexes. To see how the same
-- queries behave at production size, this script copies every real
-- accident 100 times (605,200 accidents, about 3.6 million cost rows).
--
-- Each copy gets a new report number: original * 100 + copy (0-99).
-- Everything else is identical, so value distributions (e.g. 41% Texas)
-- stay realistic. This data is synthetic and is used ONLY for
-- performance testing. It is never mixed with the real pipesafe schema.
-- =====================================================================
DROP SCHEMA IF EXISTS bench CASCADE;
CREATE SCHEMA bench;

-- Lookup and reference tables: copied as they are
CREATE TABLE bench.operator          AS SELECT * FROM pipesafe.operator;
CREATE TABLE bench.county            AS SELECT * FROM pipesafe.county;
CREATE TABLE bench.state             AS SELECT * FROM pipesafe.state;
CREATE TABLE bench.cause_category    AS SELECT * FROM pipesafe.cause_category;
CREATE TABLE bench.cause_detail      AS SELECT * FROM pipesafe.cause_detail;
CREATE TABLE bench.commodity_type    AS SELECT * FROM pipesafe.commodity_type;
CREATE TABLE bench.commodity_subtype AS SELECT * FROM pipesafe.commodity_subtype;
ALTER TABLE bench.operator          ADD PRIMARY KEY (operator_id);
ALTER TABLE bench.county            ADD PRIMARY KEY (county_id);
ALTER TABLE bench.state             ADD PRIMARY KEY (state_code);
ALTER TABLE bench.cause_category    ADD PRIMARY KEY (cause_category_id);
ALTER TABLE bench.cause_detail      ADD PRIMARY KEY (cause_detail_id);
ALTER TABLE bench.commodity_type    ADD PRIMARY KEY (commodity_type_id);
ALTER TABLE bench.commodity_subtype ADD PRIMARY KEY (commodity_subtype_id);
CREATE UNIQUE INDEX ON bench.county (state_code, county_name);

-- Fact tables: 100 copies of every real row
CREATE TABLE bench.accident AS
SELECT (a.report_number * 100 + k)::BIGINT AS report_number,
       a.report_type, a.report_received_date, a.operator_id, a.facility_id,
       a.segment_name, a.on_off_shore, a.county_id, a.city_name,
       a.latitude, a.longitude, a.accident_datetime, a.time_zone,
       a.pipe_facility_type, a.system_part_id, a.item_involved_id,
       a.installation_year, a.detection_method_id, a.commodity_subtype_id,
       a.release_type, a.unintentional_release_bbls, a.intentional_release_bbls,
       a.recovered_bbls, a.ignited, a.exploded, a.shutdown_required,
       a.public_evacuated, a.cause_detail_id, a.narrative
FROM pipesafe.accident a CROSS JOIN generate_series(0, 99) AS k;
ALTER TABLE bench.accident ADD PRIMARY KEY (report_number);

CREATE TABLE bench.accident_cost AS
SELECT (c.report_number * 100 + k)::BIGINT AS report_number, c.cost_type_id, c.amount_usd
FROM pipesafe.accident_cost c CROSS JOIN generate_series(0, 99) AS k;
ALTER TABLE bench.accident_cost ADD PRIMARY KEY (report_number, cost_type_id);

CREATE TABLE bench.casualty AS
SELECT (c.report_number * 100 + k)::BIGINT AS report_number, c.person_group, c.fatalities, c.injuries
FROM pipesafe.casualty c CROSS JOIN generate_series(0, 99) AS k;
ALTER TABLE bench.casualty ADD PRIMARY KEY (report_number, person_group);

CREATE TABLE bench.corrosion_detail AS
SELECT (d.report_number * 100 + k)::BIGINT AS report_number,
       d.visual_exam_result, d.under_cathodic_protection, d.externally_coated,
       d.corrosion_inhibitors_used, d.prior_damage
FROM pipesafe.corrosion_detail d CROSS JOIN generate_series(0, 99) AS k;
ALTER TABLE bench.corrosion_detail ADD PRIMARY KEY (report_number);

-- Same summary view as Portfolio 1 (original version, correlated subqueries)
SET search_path TO bench, public;
CREATE VIEW v_accident_summary AS
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

VACUUM ANALYZE bench.accident;
VACUUM ANALYZE bench.accident_cost;
VACUUM ANALYZE bench.casualty;
VACUUM ANALYZE bench.corrosion_detail;

SELECT 'accident' AS table_name, COUNT(*) FROM bench.accident
UNION ALL SELECT 'accident_cost', COUNT(*) FROM bench.accident_cost
UNION ALL SELECT 'casualty', COUNT(*) FROM bench.casualty
UNION ALL SELECT 'corrosion_detail', COUNT(*) FROM bench.corrosion_detail;
