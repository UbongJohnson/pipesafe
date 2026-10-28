-- 02_load_data.sql : loads the CSVs made by scripts/prepare_load.py
-- Run from the repository folder that contains load/ :
--   psql -d pipesafe -f sql/02_load_data.sql
SET search_path TO pipesafe;
\set ON_ERROR_STOP on
BEGIN;
\copy operator                   FROM 'load/operator.csv'                   CSV HEADER
\copy operator_name_history      FROM 'load/operator_name_history.csv'      CSV HEADER
\copy facility                   FROM 'load/facility.csv'                   CSV HEADER
\copy state                      FROM 'load/state.csv'                      CSV HEADER
\copy county                     FROM 'load/county.csv'                     CSV HEADER
\copy commodity_type             FROM 'load/commodity_type.csv'             CSV HEADER
\copy commodity_subtype          FROM 'load/commodity_subtype.csv'          CSV HEADER
\copy cause_category             FROM 'load/cause_category.csv'             CSV HEADER
\copy cause_detail               FROM 'load/cause_detail.csv'               CSV HEADER
\copy system_part                FROM 'load/system_part.csv'                CSV HEADER
\copy item_involved              FROM 'load/item_involved.csv'              CSV HEADER
\copy detection_method           FROM 'load/detection_method.csv'           CSV HEADER
\copy cost_type                  FROM 'load/cost_type.csv'                  CSV HEADER
\copy accident                   FROM 'load/accident.csv'                   CSV HEADER
\copy offshore_location          FROM 'load/offshore_location.csv'          CSV HEADER
\copy casualty                   FROM 'load/casualty.csv'                   CSV HEADER
\copy accident_cost              FROM 'load/accident_cost.csv'              CSV HEADER
\copy corrosion_detail           FROM 'load/corrosion_detail.csv'           CSV HEADER
\copy excavation_detail          FROM 'load/excavation_detail.csv'          CSV HEADER
\copy incorrect_operation_detail FROM 'load/incorrect_operation_detail.csv' CSV HEADER
-- keep SERIAL counters in step with the loaded ids
SELECT setval(pg_get_serial_sequence('pipesafe.facility','facility_id'), (SELECT MAX(facility_id) FROM facility));
SELECT setval(pg_get_serial_sequence('pipesafe.county','county_id'),     (SELECT MAX(county_id)   FROM county));
COMMIT;
