# Advanced Database Systems Portfolio (MIT 8103)

**Student:** Victor _[add surname and matriculation number]_
**Course:** MIT 8103 Advanced Database Systems, Miva Open University, 2026/2027 First Semester

## Case Study

**PipeSafe Analytics: Hazardous Liquid Pipeline Incident Management System.** This is a simulated pipeline safety and compliance organisation that keeps a central database of pipeline accidents reported by operators.

It is populated with real accident data from the U.S. Pipeline and Hazardous Materials Safety Administration (PHMSA): 6,052 hazardous liquid pipeline accidents from 2010 to 2026.

See [`portfolio-1-database-design/case-study.md`](portfolio-1-database-design/case-study.md) for the full description.

## Portfolio Activities

| # | Activity | Folder | What it shows |
|---|---|---|---|
| 1 | Database Design and Modelling | [`portfolio-1-database-design`](portfolio-1-database-design) | Flat 648-column file normalised to a 20-table 3NF schema; ER diagram; constraints; loaded and verified |
| 2 | Query Processing and Optimisation | [`portfolio-2-query-optimisation`](portfolio-2-query-optimisation) | 8 queries measured before/after on real and 100× scaled data; indexes, rewrites, materialised view; costs of each |
| 3 | Transactions and Concurrency | [`portfolio-3-transactions-concurrency`](portfolio-3-transactions-concurrency) | Commit, rollback, savepoint; isolation levels; lost update and deadlock with working fixes |
| 4 | NoSQL and Advanced Data Models | [`portfolio-4-nosql`](portfolio-4-nosql) | MongoDB document model holding all 242 cause-specific questions; 10 queries cross-checked against PostgreSQL |
| 5 | Distributed and Cloud Database | [`portfolio-5-distributed-cloud`](portfolio-5-distributed-cloud) | 4-server cluster: streaming replication, sync vs async, failover, region sharding; CAP trade-offs measured |

Each folder has a README explaining what was done, how to run it and what to expect, plus a write-up with the results.

## Producing the Evidence

`run_and_capture.py` runs every portfolio's steps on your own computer. It saves a screenshot (PNG) and a text copy of each step's output into that portfolio's `screenshots/` folder, stamped with the computer name and time.

```bash
pip install psycopg2-binary pymongo pandas numpy pillow

# Windows: Portfolios 1-4 (Portfolio 1 rebuilds the pipesafe database)
python run_and_capture.py --portfolios 1,2,3,4 --data PATH\TO\accident_hazardous_liquid_jan2010_present.txt --password YOUR_POSTGRES_PASSWORD --mongo "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"

# WSL / Linux: Portfolio 5
python3 run_and_capture.py --portfolios 5 --data /mnt/c/PATH/TO/accident_hazardous_liquid_jan2010_present.txt --pg-bin /usr/lib/postgresql/18/bin
```

## Tools

- **PostgreSQL 18:** relational database (Portfolios 1-3). The Portfolio 5 replication and `postgres_fdw` sharding results were recorded on a PostgreSQL 16 cluster in Linux
- **Python 3:** pandas (data preparation), psycopg2 (PostgreSQL), pymongo (MongoDB)
- **MongoDB Atlas:** document database and cloud replica set (Portfolios 4 and 5)
- **dbdiagram.io:** ER diagram

## Data Source

U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration (PHMSA). *Hazardous Liquid Accident Data, January 2010 to present.*
https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data

The full data file (17.4 MB) is not stored in this repository. Download it from the link above. A small sample is in `portfolio-1-database-design/data/sample.csv`.
