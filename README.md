# Advanced Database Systems Portfolio (MIT 8103)

**Student:** Victor _[add surname and matriculation number]_
**Course:** MIT 8103 Advanced Database Systems, Miva Open University, 2026/2027 First Semester

## Case Study

**PipeSafe Analytics: Hazardous Liquid Pipeline Incident Management System.** This is a simulated pipeline safety and compliance organisation that keeps a central database of pipeline accidents reported by operators.

It is populated with real accident data from the U.S. Pipeline and Hazardous Materials Safety Administration (PHMSA): 6,052 hazardous liquid pipeline accidents from 2010 to 2026.

See [`portfolio-1-database-design/case-study.md`](portfolio-1-database-design/case-study.md) for the full description.

## Portfolio Activities

| # | Activity | Folder | Status |
|---|---|---|---|
| 1 | Database Design and Modelling | [`portfolio-1-database-design`](portfolio-1-database-design) | In progress |
| 2 | Query Processing and Optimisation | `portfolio-2-query-optimisation` | Not started |
| 3 | Transactions and Concurrency | `portfolio-3-transactions-concurrency` | Not started |
| 4 | NoSQL and Advanced Data Models | `portfolio-4-nosql` | Not started |
| 5 | Distributed and Cloud Database | `portfolio-5-distributed-cloud` | Not started |

## Tools

- PostgreSQL 16 (relational database)
- Python 3 with pandas (data profiling and loading)
- dbdiagram.io (ER diagram)
- MongoDB (Portfolio 4, planned)

## Data Source

U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration (PHMSA). *Hazardous Liquid Accident Data, January 2010 to present.*
https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data

The full data file (17.4 MB) is not stored in this repository. Download it from the link above. A small sample is in `portfolio-1-database-design/data/sample.csv`.
