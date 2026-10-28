# Relational Schema: PipeSafe Analytics

This document describes the normalised schema built from the dataset analysis. It contains 20 tables, 21 foreign keys and 1 view.

| File | Contents |
|---|---|
| `er-diagram.png` | The ER diagram |
| `er-diagram.dbml` | Diagram source; paste into [dbdiagram.io](https://dbdiagram.io) to edit |
| `sql/01_create_tables.sql` | `CREATE TABLE` script (PostgreSQL) |

The schema was tested by loading all 6,052 real accident reports with every constraint switched on. The results are in section 7.

## 1. Tables at a Glance

| Group | Table | Rows loaded | Purpose |
|---|---|---|---|
| Central | `accident` | 6,052 | One row per accident report |
| Operators and facilities | `operator` | 361 | Pipeline companies |
| | `operator_name_history` | 416 | Every name each operator has reported under |
| | `facility` | 4,015 | Named pipelines/facilities owned by an operator |
| Location | `state` | 52 | U.S. states and territories, with Census region |
| | `county` | 977 | Counties, with cleaned names |
| | `offshore_location` | 63 | Offshore area, block and water depth |
| Lookups | `commodity_type` | 5 | Crude oil, refined products, HVL, CO₂, biofuel |
| | `commodity_subtype` | 14 | e.g. gasoline, diesel, LPG/NGL |
| | `cause_category` | 8 | e.g. corrosion failure, equipment failure |
| | `cause_detail` | 41 | e.g. internal corrosion, external corrosion |
| | `system_part` | 7 | Part of the system involved |
| | `item_involved` | 19 | Component that failed (pipe, valve, pump…) |
| | `detection_method` | 12 | How the accident was found |
| | `cost_type` | 6 | The six cost categories on the report form |
| Consequences | `casualty` | 26 | Fatalities and injuries per affected group |
| | `accident_cost` | 36,261 | Cost per accident per cost type |
| Cause detail | `corrosion_detail` | 1,328 | Extra answers for corrosion accidents |
| | `excavation_detail` | 199 | Extra answers for excavation damage |
| | `incorrect_operation_detail` | 834 | Extra answers for incorrect operation |

## 2. Relational Schema

Notation: **bold** = primary key, *italic* = foreign key, `?` = nullable.

```
operator(operator_id, operator_name, street_address?, city?, state_province?, postal_code?)
operator_name_history(operator_id*, operator_name, first_report_date, last_report_date)
    PK (operator_id, operator_name)
facility(facility_id, operator_id*, facility_name)
    UNIQUE (operator_id, facility_name)

state(state_code, state_name, region)
county(county_id, state_code*, county_name)
    UNIQUE (state_code, county_name)

commodity_type(commodity_type_id, type_name)
commodity_subtype(commodity_subtype_id, commodity_type_id*, subtype_name)
    UNIQUE (commodity_type_id, subtype_name)
cause_category(cause_category_id, category_name)
cause_detail(cause_detail_id, cause_category_id*, detail_name)
    UNIQUE (cause_category_id, detail_name)
system_part(system_part_id, part_name)
item_involved(item_involved_id, item_name)
detection_method(detection_method_id, method_name)
cost_type(cost_type_id, cost_code, description)

accident(report_number, report_type, report_received_date,
         operator_id*, facility_id*?, segment_name?, on_off_shore,
         county_id*?, city_name?, latitude, longitude,
         accident_datetime, time_zone?, pipe_facility_type,
         system_part_id*, item_involved_id*, installation_year?, detection_method_id*?,
         commodity_subtype_id*, release_type,
         unintentional_release_bbls, intentional_release_bbls?, recovered_bbls,
         ignited, exploded?, shutdown_required?, public_evacuated?,
         cause_detail_id*, narrative?)

offshore_location(report_number*, origin, adjacent_state_code*?, area_name?,
                  block_number?, water_depth_ft?, ocs_region?)
casualty(report_number*, person_group, fatalities, injuries)
    PK (report_number, person_group)
accident_cost(report_number*, cost_type_id*, amount_usd)
    PK (report_number, cost_type_id)

corrosion_detail(report_number*, visual_exam_result?, under_cathodic_protection?,
                 externally_coated?, corrosion_inhibitors_used?, prior_damage?)
excavation_detail(report_number*, excavator_type, excavator_equipment, work_performed,
                  one_call_notified, prior_notification?, root_cause_category?)
incorrect_operation_detail(report_number*, activity_category?, operator_qualified?,
                           inadequate_procedure, no_procedure, failure_to_follow_procedure)
```

In the last six tables, `report_number` is both the primary key and a foreign key to `accident`. That is what makes them one-to-one with `accident`.

## 3. Relationships and Cardinality

| Parent | Child | Cardinality | Meaning |
|---|---|---|---|
| operator | accident | 1 : many | An operator reports many accidents; each accident has exactly one operator |
| operator | facility | 1 : many | An operator owns many facilities |
| operator | operator_name_history | 1 : many | An operator can have had several names |
| facility | accident | 0..1 : many | An accident usually names a facility (129 do not) |
| state | county | 1 : many | |
| county | accident | 0..1 : many | Offshore accidents (and 58 onshore ones) have no county |
| commodity_type | commodity_subtype | 1 : many | |
| commodity_subtype | accident | 1 : many | Every accident releases one commodity |
| cause_category | cause_detail | 1 : many | |
| cause_detail | accident | 1 : many | Every accident has one cause |
| system_part / item_involved | accident | 1 : many | |
| detection_method | accident | 0..1 : many | Not recorded for 739 accidents |
| accident | casualty | 1 : 0..5 | One row per affected group |
| accident | accident_cost | 1 : 0..6 | One row per cost type |
| cost_type | accident_cost | 1 : many | |
| accident | offshore_location | 1 : 0..1 | Only for offshore accidents |
| accident | corrosion / excavation / incorrect_operation detail | 1 : 0..1 | Only for accidents with that cause |

## 4. Constraints

| Type | Where | Rule |
|---|---|---|
| **PRIMARY KEY** | Every table | Natural keys where PHMSA provides one (`report_number`, `operator_id`, `state_code`); surrogate keys (`SERIAL`) elsewhere |
| **FOREIGN KEY** | 21 relationships | `ON DELETE RESTRICT` from accidents to operators, facilities, locations and lookups, so you cannot delete an operator who still has accidents. `ON DELETE CASCADE` for child rows (costs, casualties, cause details), which have no meaning without their accident |
| **NOT NULL** | e.g. `accident_datetime`, `operator_id`, `cause_detail_id`, `latitude` | Fields every report must have |
| **UNIQUE** | e.g. `(operator_id, facility_name)`, `(state_code, county_name)` | Stops duplicate facilities, counties and lookup values |
| **CHECK (allowed values)** | `report_type`, `on_off_shore`, `release_type`, `pipe_facility_type`, `person_group`, `time_zone`, `region` | Short fixed lists are enforced with CHECK instead of a lookup table |
| **CHECK (ranges)** | Volumes, costs, casualty counts | Must be ≥ 0 |
| | `latitude`, `longitude` | Valid coordinates |
| | `installation_year` | Between 1850 and 2100 |
| **CHECK (business rules)** | `accident` | `recovered_bbls ≤ unintentional + intentional release` |
| | `accident` | Report received on or after the accident date |
| | `casualty` | A row must record at least one fatality or injury |
| | `operator_name_history` | Last report date ≥ first report date |
| **DEFAULT** | `recovered_bbls = 0`, `ignited = FALSE`, procedure flags `= FALSE` | |

## 5. Design Decisions

Each decision is based on a check run against the real data.

| # | Decision | Evidence from the data |
|---|---|---|
| 1 | **`operator` stores the current name; `operator_name_history` keeps every earlier name** | 52 operator IDs appear under more than one name (e.g. ID 1541: BP Pipelines (Alaska) became Hilcorp North Slope). One name per operator removes the update anomaly without losing history. |
| 2 | **`facility` uses a surrogate key, unique within an operator** | 148 facility names (e.g. "MIDLAND STATION") are used by more than one operator, so a name alone cannot identify a facility. |
| 3 | **Interstate/intrastate and system part stay on `accident`, not `facility`** | The dependency was tested and **does not hold**: 62 facilities have accidents recorded as both interstate and intrastate, and 355 have more than one system part. These describe the specific accident, not the facility. |
| 4 | **Every accident points to a commodity subtype; types without subtypes get a "NOT SPECIFIED" subtype** | Crude oil and CO₂ never have subtypes, and 10 refined/HVL reports leave it blank. Pointing only at the subtype means the type is reached through the subtype, avoiding a transitive dependency. Subtype names are unique only within a type, because "OTHER" appears under two types. |
| 5 | **Only `cause_detail_id` is stored on `accident`** | All 41 cause details belong to exactly one cause category, so the category is reached through the detail. |
| 6 | **The duplicated cause-type columns are dropped** | `INTERNAL_EXTERNAL`, `EQ_FAILURE_TYPE`, `EX_PARTY_TYPE`, `NATURAL_FORCE_TYPE`, `OPERATION_TYPE`, `OUTSIDE_FORCE_TYPE` and `FAILURE_TYPE` repeat the value in `CAUSE_DETAILS` word for word. They are redundant copies. |
| 7 | **Cause-specific answers go in one-to-one detail tables** | These columns are only filled for their own cause (100% of filled rows). Three detail tables are built as examples, for the causes with the most extra data. The other cause blocks follow the same pattern and are left for the document model in Portfolio 4. |
| 8 | **Casualties and costs become rows, not columns** | The source repeats the same fields for 5 person groups and 6 cost types, which is a repeating group. As rows, adding a new group or cost type needs no schema change, and totals become a simple `SUM`. |
| 9 | **Totals are calculated in the view `v_accident_summary`, not stored** | `PRPTY`, `FATAL`, `INJURE`, `IYEAR` and the yes/no casualty flags are 100% derivable from other columns. Storing them would risk inconsistency. |
| 10 | **County names are cleaned before loading** | "HARRIS" and "HARRIS COUNTY" become one county row. |
| 11 | **`state` includes a Census region** | Supports regional reports, and gives a natural shard key for Portfolio 5. |
| 12 | **Operator address uses `state_province`, not a foreign key to `state`** | Three operators are headquartered in Alberta, Canada. This was found when the first test load failed. |
| 13 | **Offshore details are in their own table** | Only 63 accidents are offshore. Their area, block and water depth would be empty for the other 5,989. |
| 14 | **Personal contact details are excluded** | Preparer, authoriser and contact names, emails and phones serve no analytical purpose (data minimisation). |

**How this differs from the candidate entities in the dataset analysis.** Two entities changed during design:
- **`Release` was merged into `accident`.** Release volumes and release type apply to every accident and depend only on `report_number`, so a separate one-to-one table would add a join without removing any redundancy.
- **`Location` was split into `state`, `county` and `offshore_location`.** The coordinates and city are unique to each accident, so they stay on `accident`. Only the repeated parts (states and counties) became tables.

## 6. Derived Values (view)

`v_accident_summary` joins the main tables and calculates:
- `accident_year`, from `accident_datetime`
- `total_cost_usd`, the sum of `accident_cost`
- `total_fatalities` and `total_injuries`, the sums of `casualty`
- `cause_category` and `commodity_type`, through their lookup tables

## 7. Test Load Results

The full dataset was loaded into PostgreSQL 16 with every constraint active, and all 6,052 reports were accepted. Totals calculated from the normalised tables match the raw file exactly:

| Measure | Raw file | Normalised database |
|---|---|---|
| Accidents | 6,052 | 6,052 |
| Barrels released (unintentional) | 1,388,888 | 1,388,888 |
| Barrels recovered | 552,028 | 552,028 |
| Total cost | $4,619,299,360 | $4,619,299,360 |
| Fatalities / injuries | 16 / 46 | 16 / 46 |

Each cause-detail table contains only accidents of its own cause, with 0 mismatches.

## 8. Notes to Confirm

- **Cost type descriptions.** These follow the order of Part D of PHMSA Form 7000-1. Check them against the field description file in the PHMSA download, especially `EST_COST_OPER_PAID` and `EST_COST_PROP_DAMAGE`.
