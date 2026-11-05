# Normalisation: From One Flat File to 3NF

This document explains step by step how the raw PHMSA file was normalised into the 20-table schema in `schema.md`. Every example uses real rows from the data.

Most examples follow one accident through every step: **report 20170094**. In February 2017, a valve left in the wrong position on Phillips 66's River Parish Pipeline System in St Charles Parish, Louisiana, released 13,465 barrels of LPG/NGL. One employee was killed and one contractor was injured.

**Notation.** `A → B` means "A determines B". In other words, if you know A, there is exactly one possible value of B. This is a *functional dependency*, and normalisation is about storing each one exactly once.

---

## 1. The Starting Point: Unnormalised Data

The source is a single table of **6,052 rows and 648 columns**. Here are some of the columns for two real reports:

| Column | Report 20170094 | Report 20260244 |
|---|---|---|
| REPORT_NUMBER | 20170094 | 20260244 |
| LOCAL_DATETIME | 2/9/2017 18:50 | 9/15/2026 8:37 |
| IYEAR | 2017 | 2026 |
| OPERATOR_ID | 31684 | 30829 |
| NAME | PHILLIPS 66 PIPELINE LLC | ENTERPRISE CRUDE PIPELINE LLC |
| OPERATOR_STREET_ADDRESS | 2331 CITYWEST BLVD | 1100 LOUISIANA STREET |
| PIPE_FAC_NAME | RIVER PARISH PIPELINE SYSTEM | PLAINS MESA FACILITY |
| ONSHORE_STATE_ABBREVIATION | LA | TX |
| ONSHORE_COUNTY_NAME | ST CHARLES | MIDLAND |
| COMMODITY_RELEASED_TYPE | HVL OR OTHER FLAMMABLE OR TOXIC FLUID… | CRUDE OIL |
| COMMODITY_SUBTYPE | LPG (LIQUEFIED PETROLEUM GAS) / NGL… | *(blank)* |
| CAUSE | INCORRECT OPERATION | CORROSION FAILURE |
| CAUSE_DETAILS | VALVE LEFT OR PLACED IN WRONG POSITION… | EXTERNAL CORROSION |
| NUM_EMP_FATALITIES … NUM_GP_FATALITIES | 1, 0, 0, 0, 0 | 0, 0, 0, 0, 0 |
| NUM_EMP_INJURIES … NUM_GP_INJURIES | 0, 1, 0, 0, 0 | 0, 0, 0, 0, 0 |
| FATAL / INJURE | 1 / 1 | 0 / 0 |
| EST_COST_OPER_PAID … EST_COST_OTHER | 0, 390636, 1443222, 2669566, 0, 0 | 0, 70, 0, 0, 37500, 0 |
| PRPTY (total cost) | 4,503,424 | 37,570 |

### Problems in this structure

**Update anomaly.** The operator's name and address are copied into every one of its accident rows. Operator 31684 reported 34 accidents as *CONOCOPHILLIPS* (2010 to April 2012), then 181 as *PHILLIPS 66 PIPELINE LLC* (May 2012 onwards), and its address changed at the same time. Correcting or updating the operator means editing hundreds of rows. Across the file, **52 operators already appear under more than one name**.

**Insertion anomaly.** A new operator, a new cause type or a new county cannot be recorded until an accident involving it happens, because the only table is a table of accidents.

**Deletion anomaly.** **115 operators have only one accident** in the file. Deleting that accident, for example because it was reported in error, would also delete everything known about the operator.

**Repeating groups.** The same pair of facts (fatalities, injuries) repeats as columns for five groups of people, and the same fact (a cost) repeats for six cost types.

**Wasted space.** 74% of the columns are more than 90% empty, because each block of cause-specific questions only applies to one type of cause.

---

## 2. First Normal Form (1NF)

**Rule:** every column holds a single value of one type, there are no repeating groups, and each row is identified by a primary key.

### Step 1.1: Choose a primary key

`REPORT_NUMBER` was checked and is unique in all 6,052 rows. The file keeps only the latest version of each report. So:

> **Primary key of the accident relation: `report_number`**

### Step 1.2: Remove repeating groups

The five casualty groups and six cost types are moved out into their own relations, with one row per accident per group or per cost type.

**Casualties for report 20170094.** Ten columns become two rows:

| report_number | person_group | fatalities | injuries |
|---|---|---|---|
| 20170094 | EMPLOYEE | 1 | 0 |
| 20170094 | CONTRACTOR | 0 | 1 |

Groups with no casualties are not stored. Across the whole dataset, **60,520 casualty cells (6,052 × 10) become 26 rows**.

**Costs for report 20260244.** Six columns become six rows:

| report_number | cost_code | amount_usd |
|---|---|---|
| 20260244 | EST_COST_OPER_PAID | 0 |
| 20260244 | EST_COST_GAS_RELEASED | 70 |
| 20260244 | EST_COST_PROP_DAMAGE | 0 |
| 20260244 | EST_COST_EMERGENCY | 0 |
| 20260244 | EST_COST_ENVIRONMENTAL | 37,500 |
| 20260244 | EST_COST_OTHER | 0 |

The key of each new relation is composite:
- **casualty:** (report_number, person_group)
- **accident_cost:** (report_number, cost_code)

A new cost type or person group is now a new row, not a new column.

### Step 1.3: Make every value atomic and of one type

| Problem found | Fix |
|---|---|
| `INSTALLATION_YEAR` mixes numbers with the word `UNKNOWN` (927 rows) | `UNKNOWN` becomes NULL; the column becomes an integer |
| 261 yes/no columns store the text `YES`/`NO` | Converted to `BOOLEAN` |
| 18 date/time columns store text such as `2/9/2017 18:50` | Converted to `DATE` / `TIMESTAMP` |
| `ADDITIONAL_NRC_REPORT_NUMBERS` holds several values in one cell in 59 rows (e.g. `1457156, 1457198`) | Outside the scope of this design, so excluded. Keeping it would require a separate table with one row per number. |

**Result after 1NF:**
```
accident(report_number, ..., operator_id, operator_name, operator_address, facility_name,
         state, county, commodity_type, commodity_subtype, cause, cause_detail, ...)
casualty(report_number, person_group, fatalities, injuries)
accident_cost(report_number, cost_code, cost_description, amount_usd)
```

The tables are now in 1NF, but the update, insertion and deletion anomalies are all still there.

---

## 3. Second Normal Form (2NF)

**Rule:** the table is in 1NF, and every non-key column depends on the **whole** primary key, not just part of it. This only matters for tables with a **composite** key.

**`accident`** has a single-column key (`report_number`), so it **cannot have a partial dependency** and is already in 2NF. Its remaining problems are dealt with in 3NF.

**`accident_cost`** has the composite key (report_number, cost_code), and it breaks 2NF:

```
(report_number, cost_code) → amount_usd          ✓ depends on the whole key
cost_code → cost_description                      ✗ depends on part of the key
```

"Emergency response" is the description of `EST_COST_EMERGENCY` whatever the accident, so storing it in every cost row would repeat it **36,261 times**. The description is moved to its own relation:

```
cost_type(cost_type_id, cost_code, description)                   6 rows
accident_cost(report_number, cost_type_id, amount_usd)       36,261 rows
```

**`casualty`** has the key (report_number, person_group). Fatalities and injuries depend on both the accident and the group, so it is already in 2NF. The group is a short fixed code, enforced with a CHECK constraint.

**`operator_name_history`** has the key (operator_id, operator_name). The first and last report dates depend on the *combination* of operator and name, so it is in 2NF.

**Result after 2NF:**
```
accident(report_number, ..., operator_id, operator_name, operator_address, ...)  (unchanged)
casualty(report_number, person_group, fatalities, injuries)
cost_type(cost_type_id, cost_code, description)
accident_cost(report_number, cost_type_id, amount_usd)
```

---

## 4. Third Normal Form (3NF)

**Rule:** the table is in 2NF, and no non-key column depends on another non-key column. A dependency of the form `key → A → B` is a **transitive dependency**, and `B` must move to a table where `A` is the key.

Each transitive dependency below was **tested against the data** before the table was split.

### 4.1 Operator details

```
report_number → operator_id → operator_name, street_address, city, state_province, postal_code
```

**Test:** each `operator_id` maps to one current name and address.

**Fix:** a new `operator` relation keyed on `operator_id`. Former names go into `operator_name_history`, so the rename is recorded once instead of in 215 rows.

| operator_id | operator_name | first_report_date | last_report_date |
|---|---|---|---|
| 31684 | CONOCOPHILLIPS | 2010-03-19 | 2012-05-18 |
| 31684 | PHILLIPS 66 PIPELINE LLC | 2012-06-21 | 2026-09-24 |

This fixes all three anomalies:
- **Update:** a rename is one row.
- **Insertion:** an operator can exist before its first accident.
- **Deletion:** deleting an accident no longer deletes the operator.

### 4.2 Cause

```
report_number → cause_detail → cause
```

**Test:** all **41 of 41** cause details belong to exactly one cause. For example, `EXTERNAL CORROSION` always means `CORROSION FAILURE`.

**Fix:** `cause_category` and `cause_detail` relations. `accident` keeps only `cause_detail_id`, and the category is reached through it.

### 4.3 Commodity

```
report_number → commodity_subtype → commodity_type
```

**Test:** the dependency holds, with two complications:
- The subtype `OTHER` appears under two different types, so a subtype name is only unique **within** its type. Key: `UNIQUE (commodity_type_id, subtype_name)`.
- Crude oil and CO₂ never have a subtype, and 10 other reports leave it blank.

**Fix:** `commodity_type` and `commodity_subtype` relations. Each type that can have no subtype gets a `NOT SPECIFIED` subtype, so every accident references exactly one subtype and reaches the type through it. Without this, `accident` would need to store both the type and the subtype, and the transitive dependency would come back.

### 4.4 Location

```
report_number → county_id → state_code → state_name, region
```

**Fix:** `state` and `county` relations. County names were cleaned before loading. For example, Harris County, Texas appears as both `HARRIS` and `HARRIS COUNTY`, which would otherwise become two counties.

### 4.5 Facility

```
report_number → (operator_id, facility_name)
```

A facility name only identifies a facility within its operator: 148 names, such as `MIDLAND STATION`, are used by more than one operator.

**Fix:** a `facility` relation with a surrogate key `facility_id`, and `UNIQUE (operator_id, facility_name)`.

### 4.6 A dependency that was tested and rejected

It seemed likely that `facility → pipe_facility_type` (interstate/intrastate) and `facility → system_part`. Both were tested and **neither holds**:
- 62 facilities have accidents recorded as both interstate and intrastate.
- 355 facilities have accidents involving more than one system part.

These values describe the accident, not the facility, so they **stay on `accident`**. Moving them would have lost information. This is why every dependency in the design was checked against the data instead of assumed.

### 4.7 Derived and duplicated columns removed

Some columns are not dependencies to move but values that can be **calculated**, or **copies** of other columns. Storing them risks the copies disagreeing with the source.

| Removed column | Why | Check |
|---|---|---|
| `IYEAR` | The year of `accident_datetime` | Matches in 6,052 of 6,052 rows |
| `PRPTY` (total cost) | Sum of the six cost columns | Matches in 100% of rows |
| `FATAL`, `INJURE` | Sums of the casualty columns | Matches in 100% of rows |
| `FATALITY_IND`, `INJURY_IND` | "Is the total above 0?" | Consistent |
| `INTERNAL_EXTERNAL`, `EQ_FAILURE_TYPE`, `EX_PARTY_TYPE`, `NATURAL_FORCE_TYPE`, `OPERATION_TYPE`, `OUTSIDE_FORCE_TYPE`, `FAILURE_TYPE` | Each repeats the value of `CAUSE_DETAILS` for its own cause | Identical values |

The view `v_accident_summary` calculates these values when they are needed.

### 4.8 Removing structural NULLs

The cause-specific questions (e.g. "was the pipe under cathodic protection?") only exist for one cause. They depend on `report_number`, so leaving them in `accident` would not break 3NF. However, it would leave hundreds of columns empty in most rows.

They are placed in **one-to-one detail tables** (`corrosion_detail`, `excavation_detail`, `incorrect_operation_detail`), each keyed on `report_number`. This is a *specialisation* (subtype) design. It also ensures a corrosion answer can only exist for a corrosion accident; this was verified with 0 mismatches after loading.

**Result after 3NF: the final schema**
```
operator(operator_id, operator_name, street_address, city, state_province, postal_code)
operator_name_history(operator_id, operator_name, first_report_date, last_report_date)
facility(facility_id, operator_id, facility_name)
state(state_code, state_name, region)
county(county_id, state_code, county_name)
commodity_type(commodity_type_id, type_name)
commodity_subtype(commodity_subtype_id, commodity_type_id, subtype_name)
cause_category(cause_category_id, category_name)
cause_detail(cause_detail_id, cause_category_id, detail_name)
system_part / item_involved / detection_method / cost_type   (lookups)
accident(report_number, report_type, report_received_date, operator_id, facility_id,
         county_id, accident_datetime, commodity_subtype_id, cause_detail_id,
         unintentional_release_bbls, recovered_bbls, ...)
offshore_location(report_number, origin, area_name, block_number, water_depth_ft, ...)
casualty(report_number, person_group, fatalities, injuries)
accident_cost(report_number, cost_type_id, amount_usd)
corrosion_detail / excavation_detail / incorrect_operation_detail(report_number, ...)
```

### Boyce–Codd Normal Form check

BCNF is a slightly stricter version of 3NF: every column that determines other columns must be a candidate key. The core tables also meet this:
- In `facility`, the only determinants are `facility_id` and `(operator_id, facility_name)`, and both are candidate keys.
- The same holds for `county` with `(state_code, county_name)`, and for the two-level lookup tables.

---

## 5. Report 20170094 After Normalisation

The single 648-column row is now spread across the tables, each fact stored once:

| Table | Row(s) |
|---|---|
| accident | report 20170094, 2017-02-09 18:50, operator 31684, facility 2611, county 316, subtype 7, cause detail 19, 13,465 bbl released, 0 recovered |
| operator | 31684, PHILLIPS 66 PIPELINE LLC, 2331 CITYWEST BLVD, HOUSTON |
| facility | 2611, operator 31684, RIVER PARISH PIPELINE SYSTEM |
| county → state | 316, ST CHARLES → LA, Louisiana, SOUTH |
| commodity_subtype → type | 7, LPG / NGL → 4, HVL OR OTHER FLAMMABLE OR TOXIC FLUID |
| cause_detail → category | 19, VALVE LEFT OR PLACED IN WRONG POSITION… → 4, INCORRECT OPERATION |
| casualty | (EMPLOYEE, 1 fatality, 0 injuries), (CONTRACTOR, 0 fatalities, 1 injury) |
| accident_cost | 6 rows totalling $4,503,424 |

The view rebuilds the original totals from these rows: year 2017, total cost $4,503,424, 1 fatality and 1 injury. These match the raw file's `IYEAR`, `PRPTY`, `FATAL` and `INJURE` exactly.

---

## 6. Anomalies Resolved

| Anomaly in the flat file | How the normalised design prevents it |
|---|---|
| Renaming an operator means editing hundreds of rows | Name stored once in `operator`; history kept in `operator_name_history` |
| An operator or cause cannot exist without an accident | `operator`, `cause_detail` and the other lookups are independent tables |
| Deleting an operator's only accident deletes the operator | Operator data is in its own table, so deleting an accident leaves it untouched; `ON DELETE RESTRICT` also stops an operator being deleted while it still has accidents |
| Totals can disagree with their parts | Totals are calculated by the view, never stored |
| A cause detail can be paired with the wrong cause | Only `cause_detail_id` is stored; the category comes through the lookup |
| The same county stored under two spellings | Cleaned names with `UNIQUE (state_code, county_name)` |

---

## 7. Deliberate Trade-offs

Full normalisation was not applied everywhere. Where the design stops short, it does so on purpose:

- **`city_name` stays as text on `accident`.** A city does not reliably determine a county in this data, and city names are unique to so few accidents that a separate city table would add joins without removing meaningful repetition.
- **Short fixed code lists use CHECK constraints, not lookup tables.** This applies to `report_type`, `release_type`, `on_off_shore`, `person_group` and `time_zone`. Each list has 2–6 short values that never change, so a lookup table would add joins for no benefit.
- **`operator.operator_name` holds the current name, which also appears in `operator_name_history`.** This small repetition is accepted so that the most common question, "what is this operator called now?", needs no extra query.

---

## 8. Summary

| | Before | After |
|---|---|---|
| Tables | 1 | 20 (plus 1 view) |
| Columns | 648 | 100 |
| Repeating groups | Casualties (10 columns), costs (6 columns) | Rows in `casualty` and `accident_cost` |
| Transitive dependencies | Operator, cause, commodity, location, facility | None |
| Derived or duplicated columns | 13 | 0 (calculated in a view) |
| Operators reported under more than one name | 52 | Each stored once, with history |
| Highest normal form | Not in 1NF | 3NF (core tables also meet BCNF) |
