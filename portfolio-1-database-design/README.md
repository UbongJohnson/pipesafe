# Portfolio 1: Database Design and Modelling

This portfolio designs a normalised relational database for PipeSafe Analytics. It starts from the raw PHMSA accident file, which is one flat table of 6,052 rows and 648 columns, and ends with 20 linked tables in third normal form (3NF).

## Contents

| File | What it contains |
|---|---|
| `case-study.md` | The organisation, its users, the data stored and the key operations |
| `dataset-analysis.md` | Profile of the raw data: size, missing values, redundancy, data quality issues |
| `schema.md` | Relational schema, relationships, constraints and design decisions |
| `er-diagram.png` | ER diagram (crow's-foot notation) |
| `er-diagram.dbml` | Source of the ER diagram; paste into [dbdiagram.io](https://dbdiagram.io) to edit |
| `scripts/data_profile.py` | Produces every figure in the dataset analysis |
| `scripts/prepare_load.py` | Splits the flat file into one CSV per normalised table |
| `sql/01_create_tables.sql` | Creates the schema, tables, keys, constraints and summary view |
| `sql/02_load_data.sql` | Loads the CSVs into PostgreSQL |
| `sql/03_verify.sql` | Checks row counts and that totals match the source file |
| `data/sample.csv` | 32 sample rows from the source (personal data removed) |
| `screenshots/` | Evidence of the database running |

## How to Run

Requirements: PostgreSQL 14 or later, Python 3, and pandas (`pip install pandas`).

1. **Download the data.** Get *Hazardous Liquid Accident Data - January 2010 to present (ZIP)* from PHMSA (link in `case-study.md`) and extract the `.txt` file.

2. **Profile the raw data.** This step is optional; it reproduces `dataset-analysis.md`.
   ```bash
   python scripts/data_profile.py path/to/accident_hazardous_liquid_jan2010_present.txt
   ```

3. **Create the database and tables.**
   ```bash
   createdb pipesafe
   psql -d pipesafe -f sql/01_create_tables.sql
   ```

4. **Prepare and load the data.** Run these from this folder.
   ```bash
   python scripts/prepare_load.py path/to/accident_hazardous_liquid_jan2010_present.txt load
   psql -d pipesafe -f sql/02_load_data.sql
   ```

5. **Verify the load.**
   ```bash
   psql -d pipesafe -f sql/03_verify.sql
   ```

## Test Results

The full dataset loads with every constraint active. Totals from the normalised tables match the raw file exactly:

| Measure | Expected (raw file) | Result |
|---|---|---|
| Accidents | 6,052 | 6,052 |
| Barrels released | 1,388,888 | 1,388,888 |
| Barrels recovered | 552,028 | 552,028 |
| Total cost | $4,619,299,360 | $4,619,299,360 |
| Fatalities / injuries | 16 / 46 | 16 / 46 |

## Key Design Decisions

- **Operators are stored once**, with a separate name history. 52 operators appear under more than one name in the raw data.
- **Cause and commodity use two-level lookup tables**, removing transitive dependencies.
- **Costs and casualties become rows instead of repeated columns** (1NF).
- **Totals are calculated in a view** rather than stored.
- **Cause-specific answers go in one-to-one detail tables**, instead of hundreds of mostly empty columns.

`schema.md` gives the full reasoning and evidence for each decision.
