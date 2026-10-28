-- =====================================================================
-- MIT 8103 Portfolio 1 - PipeSafe Analytics
-- Hazardous Liquid Pipeline Incident Management System
-- 01_create_tables.sql : normalised (3NF) schema for PostgreSQL 14+
-- Source data: PHMSA Hazardous Liquid Accident Data, Jan 2010 - present
-- =====================================================================

DROP SCHEMA IF EXISTS pipesafe CASCADE;
CREATE SCHEMA pipesafe;
SET search_path TO pipesafe;

-- ---------------------------------------------------------------------
-- 1. OPERATORS AND FACILITIES
-- ---------------------------------------------------------------------

-- One row per pipeline operator. OPERATOR_ID is PHMSA's own identifier,
-- so it is used as a natural primary key. The name and address are the
-- ones on the operator's most recent report.
CREATE TABLE operator (
    operator_id     INTEGER       PRIMARY KEY,
    operator_name   VARCHAR(150)  NOT NULL,
    street_address  VARCHAR(150),
    city            VARCHAR(80),
    state_province  VARCHAR(30),      -- not a FK: three operators are based in Alberta, Canada
    postal_code     VARCHAR(10)
);

-- Every name an operator has reported under (renames, acquisitions).
-- Fixes the update anomaly found in the dataset analysis (5.3).
CREATE TABLE operator_name_history (
    operator_id        INTEGER       NOT NULL REFERENCES operator (operator_id) ON DELETE CASCADE,
    operator_name      VARCHAR(150)  NOT NULL,
    first_report_date  DATE          NOT NULL,
    last_report_date   DATE          NOT NULL,
    PRIMARY KEY (operator_id, operator_name),
    CHECK (last_report_date >= first_report_date)
);

-- A named pipeline or facility belonging to one operator. Names are only
-- unique within an operator (148 names, e.g. "MIDLAND STATION", are used
-- by more than one operator), so a surrogate key is used.
CREATE TABLE facility (
    facility_id     SERIAL        PRIMARY KEY,
    operator_id     INTEGER       NOT NULL REFERENCES operator (operator_id) ON DELETE RESTRICT,
    facility_name   VARCHAR(200)  NOT NULL,
    UNIQUE (operator_id, facility_name)
);

-- ---------------------------------------------------------------------
-- 2. LOCATION
-- ---------------------------------------------------------------------

-- U.S. states and territories. Region (U.S. Census region) supports
-- regional reporting and the sharding discussion in Portfolio 5.
CREATE TABLE state (
    state_code  CHAR(2)      PRIMARY KEY,
    state_name  VARCHAR(40)  NOT NULL UNIQUE,
    region      VARCHAR(20)  NOT NULL
                CHECK (region IN ('NORTHEAST', 'MIDWEST', 'SOUTH', 'WEST', 'TERRITORY'))
);

-- Counties, with names cleaned (upper case, "COUNTY"/"PARISH"/"BOROUGH"
-- suffix removed) so that "HARRIS" and "HARRIS COUNTY" become one row.
CREATE TABLE county (
    county_id    SERIAL       PRIMARY KEY,
    state_code   CHAR(2)      NOT NULL REFERENCES state (state_code) ON DELETE RESTRICT,
    county_name  VARCHAR(80)  NOT NULL,
    UNIQUE (state_code, county_name)
);

-- ---------------------------------------------------------------------
-- 3. LOOKUP (REFERENCE) TABLES
-- ---------------------------------------------------------------------

CREATE TABLE commodity_type (
    commodity_type_id  SMALLSERIAL   PRIMARY KEY,
    type_name          VARCHAR(120)  NOT NULL UNIQUE
);

-- Subtype names are only unique within a type ("OTHER" appears under two
-- types). Types with no subtypes on the form (crude oil, CO2) get a
-- single 'NOT SPECIFIED' subtype, so every accident references exactly
-- one subtype and the type is reached through it (no transitive dependency).
CREATE TABLE commodity_subtype (
    commodity_subtype_id  SMALLSERIAL   PRIMARY KEY,
    commodity_type_id     SMALLINT      NOT NULL REFERENCES commodity_type (commodity_type_id) ON DELETE RESTRICT,
    subtype_name          VARCHAR(120)  NOT NULL,
    UNIQUE (commodity_type_id, subtype_name)
);

CREATE TABLE cause_category (
    cause_category_id  SMALLSERIAL  PRIMARY KEY,
    category_name      VARCHAR(60)  NOT NULL UNIQUE
);

-- Every cause detail belongs to exactly one category (verified: 41 of 41).
CREATE TABLE cause_detail (
    cause_detail_id    SMALLSERIAL   PRIMARY KEY,
    cause_category_id  SMALLINT      NOT NULL REFERENCES cause_category (cause_category_id) ON DELETE RESTRICT,
    detail_name        VARCHAR(200)  NOT NULL,
    UNIQUE (cause_category_id, detail_name)
);

CREATE TABLE system_part (
    system_part_id  SMALLSERIAL   PRIMARY KEY,
    part_name       VARCHAR(120)  NOT NULL UNIQUE
);

CREATE TABLE item_involved (
    item_involved_id  SMALLSERIAL  PRIMARY KEY,
    item_name         VARCHAR(80)  NOT NULL UNIQUE
);

CREATE TABLE detection_method (
    detection_method_id  SMALLSERIAL   PRIMARY KEY,
    method_name          VARCHAR(150)  NOT NULL UNIQUE
);

CREATE TABLE cost_type (
    cost_type_id   SMALLSERIAL   PRIMARY KEY,
    cost_code      VARCHAR(30)   NOT NULL UNIQUE,   -- source column, e.g. EST_COST_EMERGENCY
    description    VARCHAR(150)  NOT NULL
);

-- ---------------------------------------------------------------------
-- 4. ACCIDENT (central table) - one row per PHMSA accident report
-- ---------------------------------------------------------------------
-- Not stored because they can be derived: accident year (IYEAR), total
-- cost (PRPTY), total fatalities/injuries (FATAL, INJURE), the yes/no
-- casualty flags, cause category and commodity type.

CREATE TABLE accident (
    report_number               BIGINT        PRIMARY KEY,
    report_type                 VARCHAR(20)   NOT NULL
        CHECK (report_type IN ('ORIGINAL', 'SUPPLEMENTAL', 'ORIGINAL FINAL', 'SUPPLEMENTAL FINAL')),
    report_received_date        DATE          NOT NULL,

    -- who and where
    operator_id                 INTEGER       NOT NULL REFERENCES operator (operator_id) ON DELETE RESTRICT,
    facility_id                 INTEGER       REFERENCES facility (facility_id) ON DELETE RESTRICT,
    segment_name                VARCHAR(200),
    on_off_shore                VARCHAR(8)    NOT NULL CHECK (on_off_shore IN ('ONSHORE', 'OFFSHORE')),
    county_id                   INTEGER       REFERENCES county (county_id) ON DELETE RESTRICT,
    city_name                   VARCHAR(80),
    latitude                    NUMERIC(9,6)  NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude                   NUMERIC(9,6)  NOT NULL CHECK (longitude BETWEEN -180 AND 180),

    -- when
    accident_datetime           TIMESTAMP     NOT NULL,       -- local time at the site
    time_zone                   VARCHAR(10)                   -- only collected from 2021 onwards
        CHECK (time_zone IN ('EASTERN', 'CENTRAL', 'MOUNTAIN', 'PACIFIC', 'ALASKA', 'HAWAII')),

    -- what failed
    pipe_facility_type          VARCHAR(10)   NOT NULL CHECK (pipe_facility_type IN ('INTERSTATE', 'INTRASTATE')),
    system_part_id              SMALLINT      NOT NULL REFERENCES system_part (system_part_id),
    item_involved_id            SMALLINT      NOT NULL REFERENCES item_involved (item_involved_id),
    installation_year           SMALLINT      CHECK (installation_year BETWEEN 1850 AND 2100),
    detection_method_id         SMALLINT      REFERENCES detection_method (detection_method_id),

    -- what was released
    commodity_subtype_id        SMALLINT      NOT NULL REFERENCES commodity_subtype (commodity_subtype_id),
    release_type                VARCHAR(25)   NOT NULL
        CHECK (release_type IN ('LEAK', 'RUPTURE', 'MECHANICAL PUNCTURE', 'OVERFILL OR OVERFLOW', 'OTHER')),
    unintentional_release_bbls  NUMERIC(12,2) NOT NULL CHECK (unintentional_release_bbls >= 0),
    intentional_release_bbls    NUMERIC(12,2) CHECK (intentional_release_bbls >= 0),
    recovered_bbls              NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (recovered_bbls >= 0),

    -- consequences
    ignited                     BOOLEAN       NOT NULL DEFAULT FALSE,
    exploded                    BOOLEAN,
    shutdown_required           BOOLEAN,
    public_evacuated            INTEGER       CHECK (public_evacuated >= 0),

    -- why
    cause_detail_id             SMALLINT      NOT NULL REFERENCES cause_detail (cause_detail_id),
    narrative                   TEXT,

    -- table-level rules
    CONSTRAINT chk_recovered_not_more_than_released
        CHECK (recovered_bbls <= unintentional_release_bbls + COALESCE(intentional_release_bbls, 0)),
    CONSTRAINT chk_report_after_accident
        CHECK (report_received_date >= accident_datetime::date)
);

-- Offshore accidents only (63 rows): offshore area/block replace the
-- onshore county and city.
CREATE TABLE offshore_location (
    report_number        BIGINT        PRIMARY KEY REFERENCES accident (report_number) ON DELETE CASCADE,
    origin               VARCHAR(60)   NOT NULL
        CHECK (origin IN ('IN STATE WATERS', 'ON THE OUTER CONTINENTAL SHELF (OCS)')),
    adjacent_state_code  CHAR(2)       REFERENCES state (state_code),
    area_name            VARCHAR(80),
    block_number         VARCHAR(30),
    water_depth_ft       NUMERIC(8,1)  CHECK (water_depth_ft >= 0),
    ocs_region           VARCHAR(60)
);

-- ---------------------------------------------------------------------
-- 5. CASUALTIES AND COSTS (repeating groups reshaped into rows - 1NF)
-- ---------------------------------------------------------------------

-- One row per accident per affected group. Only groups with at least one
-- fatality or injury are stored.
CREATE TABLE casualty (
    report_number  BIGINT       NOT NULL REFERENCES accident (report_number) ON DELETE CASCADE,
    person_group   VARCHAR(20)  NOT NULL
        CHECK (person_group IN ('EMPLOYEE', 'CONTRACTOR', 'EMERGENCY_RESPONDER', 'OTHER_WORKER', 'PUBLIC')),
    fatalities     SMALLINT     NOT NULL DEFAULT 0 CHECK (fatalities >= 0),
    injuries       SMALLINT     NOT NULL DEFAULT 0 CHECK (injuries   >= 0),
    PRIMARY KEY (report_number, person_group),
    CHECK (fatalities + injuries > 0)
);

-- One row per accident per cost type (six cost types on the form).
CREATE TABLE accident_cost (
    report_number  BIGINT         NOT NULL REFERENCES accident (report_number) ON DELETE CASCADE,
    cost_type_id   SMALLINT       NOT NULL REFERENCES cost_type (cost_type_id),
    amount_usd     NUMERIC(14,2)  NOT NULL CHECK (amount_usd >= 0),
    PRIMARY KEY (report_number, cost_type_id)
);

-- ---------------------------------------------------------------------
-- 6. CAUSE-SPECIFIC DETAIL (specialisation, one-to-one with accident)
-- These answers only exist for one cause each, so they are kept out of
-- the accident table instead of leaving hundreds of NULL columns.
-- ---------------------------------------------------------------------

CREATE TABLE corrosion_detail (
    report_number               BIGINT       PRIMARY KEY REFERENCES accident (report_number) ON DELETE CASCADE,
    visual_exam_result          VARCHAR(20)  CHECK (visual_exam_result IN ('LOCALIZED PITTING', 'GENERAL CORROSION', 'OTHER')),
    under_cathodic_protection   BOOLEAN,
    externally_coated           BOOLEAN,
    corrosion_inhibitors_used   BOOLEAN,
    prior_damage                VARCHAR(40)
);

CREATE TABLE excavation_detail (
    report_number          BIGINT       PRIMARY KEY REFERENCES accident (report_number) ON DELETE CASCADE,
    excavator_type         VARCHAR(60)  NOT NULL,
    excavator_equipment    VARCHAR(60)  NOT NULL,
    work_performed         VARCHAR(80)  NOT NULL,
    one_call_notified      BOOLEAN      NOT NULL,
    prior_notification     BOOLEAN,
    root_cause_category    VARCHAR(60)
);

CREATE TABLE incorrect_operation_detail (
    report_number                BIGINT       PRIMARY KEY REFERENCES accident (report_number) ON DELETE CASCADE,
    activity_category            VARCHAR(80),
    operator_qualified           BOOLEAN,
    inadequate_procedure         BOOLEAN      NOT NULL DEFAULT FALSE,
    no_procedure                 BOOLEAN      NOT NULL DEFAULT FALSE,
    failure_to_follow_procedure  BOOLEAN      NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------
-- 7. VIEW - derived values calculated instead of stored
-- ---------------------------------------------------------------------

CREATE VIEW v_accident_summary AS
SELECT a.report_number,
       EXTRACT(YEAR FROM a.accident_datetime)::INT                 AS accident_year,
       a.accident_datetime,
       o.operator_name,
       cc.category_name                                            AS cause_category,
       cd.detail_name                                              AS cause_detail,
       ct.type_name                                                AS commodity_type,
       a.unintentional_release_bbls,
       a.recovered_bbls,
       COALESCE((SELECT SUM(c.amount_usd)  FROM accident_cost c WHERE c.report_number = a.report_number), 0) AS total_cost_usd,
       COALESCE((SELECT SUM(x.fatalities)  FROM casualty x      WHERE x.report_number = a.report_number), 0) AS total_fatalities,
       COALESCE((SELECT SUM(x.injuries)    FROM casualty x      WHERE x.report_number = a.report_number), 0) AS total_injuries
FROM accident a
JOIN operator          o  ON o.operator_id           = a.operator_id
JOIN cause_detail      cd ON cd.cause_detail_id      = a.cause_detail_id
JOIN cause_category    cc ON cc.cause_category_id    = cd.cause_category_id
JOIN commodity_subtype cs ON cs.commodity_subtype_id = a.commodity_subtype_id
JOIN commodity_type    ct ON ct.commodity_type_id    = cs.commodity_type_id;
