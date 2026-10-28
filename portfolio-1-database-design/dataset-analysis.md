# Dataset Analysis: PHMSA Hazardous Liquid Accident Data (2010–2026)

This section describes the raw data before any design work. Its findings drive the entity list, the normalisation steps and the constraints in the rest of Portfolio 1.

All figures were produced by `scripts/data_profile.py`. The script can be re-run on the source file to reproduce every number below.

## 1. Source File

| Property | Value |
|---|---|
| Publisher | U.S. DOT, Pipeline and Hazardous Materials Safety Administration (PHMSA) |
| File | `accident_hazardous_liquid_jan2010_present.txt` |
| Downloaded | 26 October 2026, from the PHMSA *Distribution, Transmission & Gathering, LNG, and Liquid Accident and Incident Data* page |
| Format | Tab-delimited text, UTF-8, Windows (CRLF) line endings |
| Size | 17.4 MB |
| Rows | **6,052** accident reports |
| Columns | **648** |
| Accident date range | 1 January 2010 to 18 September 2026 (2026 is a partial year) |
| Grain | One row per accident report. `REPORT_NUMBER` is unique in every row. |

**Report versions.** Operators can file supplemental reports as an investigation progresses, but the file keeps only the **latest version** of each report. The `REPORT_TYPE` column shows that version's status:

| REPORT_TYPE | Rows | Meaning |
|---|---|---|
| SUPPLEMENTAL FINAL | 4,475 | Updated at least once; now closed |
| ORIGINAL FINAL | 1,336 | Filed once; closed |
| ORIGINAL | 121 | Still open; not yet updated |
| SUPPLEMENTAL | 120 | Updated but still open |

So 241 reports (4%) are still open and may change. This matters for Portfolio 3, where updating an open report is a realistic transaction.

## 2. Accidents per Year

| Year | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 |
|---|---|---|---|---|---|---|---|---|---|
| Accidents | 350 | 344 | 367 | 400 | 455 | 460 | 420 | 415 | 405 |

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|
| Accidents | 384 | 332 | 347 | 295 | 299 | 287 | 269 | 223 |

\* January to September only.

Accidents peaked in 2014–2015 and have fallen steadily since.

## 3. What the 648 Columns Contain

The file mirrors PHMSA Form 7000-1. Every section of the form becomes a block of columns in a single flat table.

| Column group | Columns | Examples |
|---|---|---|
| Report administration | 5 | `REPORT_NUMBER`, `REPORT_TYPE`, `REPORT_RECEIVED_DATE`, `IYEAR` |
| Operator | 6 | `OPERATOR_ID`, `NAME`, street, city, state, postal code |
| Time and coordinates | 5 | `LOCAL_DATETIME`, `TIME_ZONE`, latitude, longitude |
| Commodity | 5 | `COMMODITY_RELEASED_TYPE`, `COMMODITY_SUBTYPE` |
| Release volumes | 3 | Unintentional, intentional and recovered barrels |
| Casualties | 14 | Fatalities and injuries for each group (employees, contractors, responders, workers, public) |
| Detection, shutdown and response | 40 | How identified, shutdown/restart times, ignition, explosion, valve closure |
| Location and crossings | 37 | Facility name, state, county, city, road/rail/water crossings, offshore areas |
| Pipe and equipment involved | 54 | Item involved, pipe diameter, wall thickness, coating, valves, pumps, tanks |
| Release type | 10 | Leak, rupture, puncture, overfill |
| Environmental impact | 33 | Wildlife, soil, water contamination, high consequence areas |
| Costs | 8 | Property damage, emergency response, environmental remediation, total |
| Public impact | 4 | Hospitalisations, buildings affected |
| Pressure, inspection and leak detection | 38 | Operating pressure, SCADA, CPM leak detection |
| Investigation and drug testing | 20 | Investigation status, control room findings |
| Cause-specific detail | 213 | Separate question blocks for corrosion, excavation, natural force, equipment failure and so on |
| Integrity inspection history | 89 | In-line inspection tools, hydrotests, direct assessment |
| Cause sub-flags | 50 | Yes/no flags summarising the cause blocks |
| Report preparer and contacts | 13 | Names, titles, emails, phone numbers |
| Narrative | 1 | Free-text description of the accident (average about 950 characters) |

## 4. Headline Figures

| Measure | Value |
|---|---|
| Operators (unique `OPERATOR_ID`) | 361 |
| States with onshore accidents | 48 (plus 63 offshore accidents) |
| Distinct facility names | 3,822 |
| Barrels released unintentionally | 1,388,888 |
| Barrels recovered | 552,028 (about 40% of unintentional releases) |
| Total reported cost | $4.62 billion |
| Fatalities / injuries | 16 / 46 |
| Accidents involving fire | 201 |

**Where and why accidents happen.**
- **Texas** has 2,477 accidents (41% of all accidents), followed by Oklahoma (481) and Louisiana (373).
- **Crude oil** accounts for 51% of releases, followed by refined products (32%) and HVLs (16%).
- **Equipment failure** is the most common cause (46%), followed by corrosion (22%) and incorrect operation (14%).
- The largest operator is Enterprise Crude Pipeline LLC, with 423 accidents.

## 5. Data Quality Issues

### 5.1 The table is extremely sparse

| Share of values missing | Columns |
|---|---|
| 0% (always filled) | 38 |
| Under 10% | 28 |
| 10–50% | 29 |
| 50–90% | 72 |
| 90–99% | 180 |
| Over 99% | 301 |

Only **66 of 648 columns** are at least 90% complete. **481 columns (74%) are more than 90% empty**, and **32 columns are completely empty**, for example `BLEND_DETAILS`, `OSF_TORNADO_IND` and `CPCM_IND`.

### 5.2 Columns only apply to some accidents

The sparsity is structural, not careless. Most blocks of columns only apply to one kind of accident. The cause blocks show this most clearly:

| Column | Rows filled | Filled only when CAUSE is… |
|---|---|---|
| `INTERNAL_EXTERNAL` | 1,328 | Corrosion failure (100%) |
| `EQ_FAILURE_TYPE` | 2,759 | Equipment failure (100%) |
| `OPERATION_TYPE` | 834 | Incorrect operation (100%) |
| `NATURAL_FORCE_TYPE` | 264 | Natural force damage (100%) |
| `EX_PARTY_TYPE` | 199 | Excavation damage (100%) |
| `OUTSIDE_FORCE_TYPE` | 128 | Other outside force damage (100%) |

Every accident carries all 213 cause columns, but only its own cause's block is used. Offshore location columns are likewise only filled for the 63 offshore accidents, and tank columns only when a tank was involved.

**Design implication:** the central `Accident` table should hold only the attributes that apply to every accident. Cause-specific detail belongs in separate tables linked one-to-one to `Accident`. This varying structure is also the main argument for the document model in Portfolio 4.

### 5.3 Operator names are inconsistent (update anomaly)

- 361 operator IDs map to **413 different names**.
- **52 operator IDs appear under more than one name**, and **75 under more than one address**.

These are mostly renames and acquisitions:

| OPERATOR_ID | Names used in the file |
|---|---|
| 30829 | ENTERPRISE CRUDE PIPELINE LLC; TEPPCO CRUDE PIPELINE, LLC |
| 31684 | CONOCOPHILLIPS; PHILLIPS 66 PIPELINE LLC |
| 22855 | FLINT HILLS RESOURCES, LC; KOCH PIPELINE COMPANY, L.P. |
| 32109 | ONEOK NGL PIPELINE LP; ONEOK NGL PIPELINE, LLC |
| 12624 | MOBIL CORP; EXXONMOBIL OIL CORPORATION |

Because the name is copied into every accident row, a rename has to be made in hundreds of rows at once. If any are missed, the same company appears under two names. This is the classic **update anomaly** that normalisation removes.

**Design implication:** `Operator` becomes its own table keyed on `OPERATOR_ID`, with the name stored once. An optional `OperatorNameHistory` table can keep former names.

### 5.4 Heavy repetition of operator details

Enterprise Crude Pipeline LLC alone repeats the same operator ID, name, street, city, state and postal code in **423 rows**:

| REPORT_NUMBER | OPERATOR_ID | NAME | STREET | CITY | STATE | POSTAL |
|---|---|---|---|---|---|---|
| 20260244 | 30829 | ENTERPRISE CRUDE PIPELINE LLC | 1100 LOUISIANA STREET | HOUSTON | TX | 77002 |
| 20260229 | 30829 | ENTERPRISE CRUDE PIPELINE LLC | 1100 LOUISIANA STREET | HOUSTON | TX | 77002 |
| 20260227 | 30829 | ENTERPRISE CRUDE PIPELINE LLC | 1100 LOUISIANA STREET | HOUSTON | TX | 77002 |
| 20260213 | 30829 | ENTERPRISE CRUDE PIPELINE LLC | 1100 LOUISIANA STREET | HOUSTON | TX | 77002 |

The same happens with long category labels. For example, the cause detail *"VALVE LEFT OR PLACED IN WRONG POSITION, BUT NOT RESULTING IN A TANK, VESSEL, OR SUMP/SEPARATOR OVERFLOW OR FACILITY OVERPRESSURE"* (128 characters) is stored in full 165 times.

### 5.5 Hidden dependencies between columns

- **Cause detail → cause.** All 41 `CAUSE_DETAILS` values belong to exactly one `CAUSE`. For example, "INTERNAL CORROSION" always means "CORROSION FAILURE". Storing both in `Accident` creates a **transitive dependency** (`REPORT_NUMBER → CAUSE_DETAILS → CAUSE`), which 3NF removes.
- **Commodity subtype → commodity type.** This mostly holds too. The exception is the subtype "OTHER", which appears under more than one commodity type. A subtype is therefore only unique *within* its commodity type, so the lookup table needs a composite key or its own surrogate ID.
- **Operator ID → name and address.** This is the partial and transitive dependency described in 5.3.

### 5.6 Derived (calculated) columns

| Column | How it is derived | Check |
|---|---|---|
| `PRPTY` (total cost) | Sum of the six `EST_COST_*` columns | Matches in 100% of rows |
| `FATAL` | Sum of the five `NUM_*_FATALITIES` columns | Matches in 100% of rows |
| `INJURE` | Sum of the five `NUM_*_INJURIES` columns | Matches in 100% of rows |
| `FATALITY_IND`, `INJURY_IND` | YES when the total is above 0 | Consistent |

Storing derived values risks them drifting out of step with their source columns. The design will store only the component values and calculate totals in a **view**.

### 5.7 Inconsistent text values

- **County names:** 892 raw spellings collapse to **776** after making case consistent and removing "COUNTY", "PARISH" or "BOROUGH" suffixes. For example, Harris County, TX appears as both `HARRIS` (450 rows) and `HARRIS COUNTY` (6 rows).
- **Placeholder text in a numeric column:** `INSTALLATION_YEAR` contains the word `UNKNOWN` in 927 rows. These will be loaded as `NULL` so the column can be typed as an integer.

### 5.8 Data types stored as text

- **Yes/No flags:** 261 columns store `YES`/`NO` text. These will become `BOOLEAN`.
- **Dates and times:** 18 columns store text like `9/18/2026 10:26` (M/D/YYYY H:MM). These will become `TIMESTAMP`/`DATE`, with the time zone kept in its own column.
- **Numbers:** volumes, costs and coordinates are text in the file. All parse cleanly as numbers.

### 5.9 Structural gaps (not errors)

- **Offshore accidents** (63 rows) have no onshore state, county or city. They use offshore area/block fields instead. `Location` will therefore allow a NULL state for offshore records.
- **Operator type** (employee or contractor who caused it) is missing in 2,194 rows, because the form only asks it for certain causes.

### 5.10 Personal data

Thirteen columns hold the names, job titles, emails and phone numbers of the people who **prepared, authorised or are the local contact** for each report. These details have no analytical value for this system, and storing them would mean holding personal data without need. They are **excluded from the database design**, in line with data-minimisation principles (GDPR, and Nigeria's NDPA 2023).

### 5.11 Checks that passed

The core data is reliable:

| Check | Result |
|---|---|
| Duplicate report numbers | None (6,052 unique) |
| Negative volumes or costs | None |
| Recovered volume larger than released volume | None |
| Coordinates outside the U.S. range | None (latitude 18.4 to 70.3, longitude all negative) |
| `IYEAR` different from the accident date's year | None |
| Report received before the accident happened | None |
| Accidents with no cause recorded | None |

**Outliers.** Some costs are extreme. The largest single emergency response cost is $458 million, and the largest environmental cost is $635 million. These are genuine major spills rather than data errors, so they are kept. They explain the cost spikes in 2010 ($1.08 billion) and 2022 ($763 million), and they are a reason to use the median as well as the mean in the Portfolio 2 analysis.

## 6. Scope Decisions for the Design

| Column group | Decision | Reason |
|---|---|---|
| Report admin, operator, time, coordinates, commodity, volumes, casualties, costs | **Core relational tables** | Apply to every accident; central to the system's purpose |
| Location (onshore and offshore), system part, item involved, release type | **Core relational tables** | Needed for search and trend reports |
| Cause and cause detail (top two levels) | **Core lookup tables** | Every accident has one; used in nearly all analysis |
| Cause-specific question blocks (213 columns) | **Selected fields only**, in one-to-one detail tables | Only apply to one cause each; full detail is better suited to the document model in Portfolio 4 |
| Integrity inspection history, pressure, SCADA | **Excluded from the relational core** | Mostly empty and highly technical; candidates for Portfolio 4 |
| Narrative | **Kept**, as `TEXT` on `Accident` | Useful for text search |
| Preparer and contact details | **Excluded** | Personal data with no analytical use |
| 32 completely empty columns | **Excluded** | No data |

## 7. Candidate Entities

From the analysis, the normalised design will be built around these entities. They are finalised in the ER diagram.

| Entity | Comes from | Key |
|---|---|---|
| `Operator` | `OPERATOR_ID`, `NAME`, address fields | `operator_id` |
| `Facility` | `PIPE_FAC_NAME`, `SEGMENT_NAME`, system part, interstate/intrastate | Surrogate `facility_id` |
| `Location` | State, county, city, coordinates, onshore/offshore | Surrogate `location_id` |
| `Accident` | `REPORT_NUMBER`, date/time, report type, narrative | `report_number` |
| `CommodityType` / `CommoditySubtype` | Commodity columns | Surrogate IDs |
| `CauseCategory` / `CauseDetail` | `CAUSE`, `CAUSE_DETAILS` | Surrogate IDs |
| `Release` | Unintentional, intentional and recovered barrels; release type | `report_number` (one-to-one) |
| `Casualty` | The 10 fatality and injury count columns, reshaped to one row per group | (`report_number`, `person_group`) |
| `AccidentCost` | The six `EST_COST_*` columns, reshaped to one row per cost type | (`report_number`, `cost_type`) |

Reshaping casualties and costs from fixed columns into rows is a deliberate 1NF step. The original layout is a **repeating group**: five near-identical column pairs for each person group, and six columns for each cost type. In the new layout, a new person group or cost type is just a new row rather than a schema change.

## 8. Files

| File | Purpose |
|---|---|
| `scripts/data_profile.py` | Reproduces every figure in this analysis |
| `data/sample.csv` | 32 sample rows (4 per cause) with 30 core columns; personal data removed |

The full 17.4 MB source file is not committed to the repository. It can be downloaded from PHMSA (see the case study's data source section).
