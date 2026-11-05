# NoSQL Data Model: PipeSafe Accident Reports in MongoDB

This portfolio models the same PipeSafe case study as a **document database (MongoDB)**. It explains why a document model fits accident reports, shows the design and the queries, and compares the result with the relational design from Portfolio 1.

## 1. Why a Document Model Suits This Data

Portfolio 1 found three things about the PHMSA data that a relational schema handles awkwardly.

**1. Every accident has a different shape.** The report form has 213 cause-specific questions, plus inspection-history and environmental blocks. Which questions apply depends on the cause.
- Across all accidents, operators answered **242 different cause questions**.
- A typical accident answers only **4** of them (median), and the maximum is 28.
- Query N6 shows each cause category uses its own set: corrosion accidents use 69 different questions, natural-force accidents 18.

In a table, this becomes hundreds of mostly empty columns: 74% of the raw file's columns are more than 90% empty. The Portfolio 1 design kept only three cause-detail tables with a handful of fields each, and left the rest out. **A document stores exactly the questions that were answered, and nothing else.**

**2. An accident report is read and written as one unit.** An investigator opens a whole report: operator, location, what was released, who was hurt, what it cost and why it happened. In the relational design this means joining **11 tables**: `accident`, `operator`, `facility`, `county`, `state`, `commodity_subtype`, `commodity_type`, `cause_detail`, `cause_category`, `casualty` and `accident_cost`. In MongoDB it is **one read** (query N1).

**3. The report format changes over time.** PHMSA redesigned the form in 2010, which is why Portfolio 1 had to exclude the 2002–2009 records. Each document carries `schema_version: 2`. Older-format reports could be stored in the same collection with `schema_version: 1` and their own fields, with no table redesign or migration.

## 2. The Design

### Collections

| Collection | Documents | One document is… |
|---|---|---|
| `accidents` | 6,052 | One complete accident report |
| `operators` | 361 | One pipeline operator, with its full name history |

### An accident document (report 20170094, shortened)

```json
{
  "_id": 20170094,
  "schema_version": 2,
  "report":   { "type": "SUPPLEMENTAL FINAL", "received": ISODate("2017-03-10") },
  "accident_datetime": ISODate("2017-02-09T18:50:00"),
  "operator": { "id": 31684, "name": "PHILLIPS 66 PIPELINE LLC" },
  "facility": "RIVER PARISH PIPELINE SYSTEM",
  "location": {
    "on_off_shore": "ONSHORE", "state": "LA", "county": "ST CHARLES", "city": "PARADIS",
    "geo": { "type": "Point", "coordinates": [-90.449469, 29.859893] }
  },
  "commodity": { "type": "HVL OR OTHER FLAMMABLE OR TOXIC FLUID…", "subtype": "LPG … / NGL …" },
  "release":   { "type": "OTHER", "unintentional_bbls": 13465.0, "recovered_bbls": 0.0, "ignited": true },
  "casualties": [
    { "group": "EMPLOYEE",   "fatalities": 1, "injuries": 0 },
    { "group": "CONTRACTOR", "fatalities": 0, "injuries": 1 }
  ],
  "costs": { "commodity_lost": 390636.0, "operator_property_damage": 1443222.0,
             "emergency_response": 2669566.0, … },
  "total_cost_usd": 4503424.0,
  "cause": {
    "category": "INCORRECT OPERATION",
    "detail": "VALVE LEFT OR PLACED IN WRONG POSITION…",
    "answers": { "category_type": "ROUTINE MAINTENANCE",
                 "operator_qualification_ind": true,
                 "related_failure_follow_ind": true, … }
  },
  "environment": { "could_be_hca": true, "commodity_reached_hca": true, … },
  "narrative": "…"
}
```

Compare an **external corrosion** accident (report 20260244, in `data/sample_documents.json`). Its `cause.answers` holds completely different questions, such as `cathodic_pro_start_year: 1990`, `galvanic_corrosion_ind` and `cp_annual_survey_year`. It also has an `inspection_history` section that the valve accident does not have. Both documents live in the same collection.

### Embed or reference?

The key decision in document design is whether related data goes **inside** the document (embedding) or in another collection that it points to (referencing).

| Data | Decision | Reason |
|---|---|---|
| Casualties | **Embed** (array) | At most 5 entries, always shown with the accident, never queried alone |
| Costs | **Embed** (sub-document) | Fixed set of 6 types, owned by one accident |
| Cause answers | **Embed** | Belong to one accident; varying shape is exactly what documents handle well |
| Location, commodity, release | **Embed** | One-to-one with the accident |
| Cause category, commodity type | **Store the value**, not an ID | Small fixed lists that almost never change. Saves a lookup on every read. Renaming one would need an `updateMany`. |
| Operator name | **Embed a snapshot** (`id` + name *as reported*) | Shows who the operator was when the report was filed: correct for a historical record, and no lookup needed |
| Operator details and history | **Reference** (`operators` collection) | Operators are shared by many accidents (Enterprise Crude has 423). Embedding the accident list *in* the operator would make it grow without limit, a known MongoDB anti-pattern. |

### Indexes

| Index | Supports |
|---|---|
| `{ "operator.id": 1, accident_datetime: -1 }` | One operator's history, newest first (N7). Same idea as the Portfolio 2 composite index. |
| `{ "location.state": 1, accident_datetime: -1 }` | Searches by state and date |
| `{ "cause.category": 1, "cause.detail": 1 }` | Cause analysis (N2) |
| `{ total_cost_usd: -1 }` | "Costliest accidents" reports |
| `{ "location.geo": "2dsphere" }` | Distance searches (N10) |

### Schema validation

"Schema-less" does not mean "no rules". The collection is created with a `$jsonSchema` validator (`scripts/load_mongodb.py`). It requires every accident to have:
- a report number, `schema_version`, report details, date, operator, location, release and cause;
- release volumes that are non-negative numbers, and an operator `id` and `name`.

The **core** is enforced, while `cause.answers`, `environment` and `inspection_history` stay flexible.

## 3. Implementation and Testing

| Step | Script | Result |
|---|---|---|
| Build documents from the raw PHMSA file | `scripts/build_documents.py` | 6,052 accident and 361 operator documents; median accident document 2.4 KB, largest 7.5 KB |
| Check every document against the validator rules | `scripts/check_documents.py` | 6,052 checked, **0 problems** |
| Load into MongoDB Atlas, create indexes | `scripts/load_mongodb.py` | Collection created **with** the `$jsonSchema` validator; 6,052 accidents and 361 operators loaded; **all 5 indexes** created, including `2dsphere` |
| Run all 10 queries on Atlas | `scripts/run_queries.py`, `queries.js` | `results/query_results_atlas.txt`: all 10 correct |
| Earlier test runs (see below) | `scripts/run_queries.py`, `scripts/test_with_mongomock.py` | `results/query_results_ferretdb.txt`, `results/query_results_mongomock.txt` |

**Final evidence: MongoDB Atlas** (free M0 tier, MongoDB 8.0.37, 3-node replica set). Every feature the design relies on worked there: the schema validator, all five indexes, `$objectToArray` (N6) and `$geoWithin` (N10). N10 returned **178** accidents within 25 km of Cushing, matching the answer calculated independently beforehand with the haversine distance formula.

**Earlier test engines.** Before Atlas was available, the scripts were tested on two MongoDB-compatible engines. Their gaps show why the final run had to be on real MongoDB:
- **FerretDB 1.24**, an open-source server that speaks MongoDB's protocol and stores data in PostgreSQL. It ran N1, N2, N5, N7, N8 and N9 correctly, but does not support schema validators, `2dsphere` indexes, `$objectToArray` or `$geoWithin`, and returned 0 for `$sum` over nested fields (N3, N4).
- **mongomock 4.3**, an in-memory implementation of MongoDB's query engine. It ran every query except the geospatial one (N10), with the same results as Atlas.

### Cross-check with PostgreSQL

The same questions asked of both databases give the same answers:

| Question | PostgreSQL (Portfolios 1–2) | MongoDB (N-query) | Match |
|---|---|---|---|
| Accidents, barrels and cost per cause category (8 rows) | e.g. Material failure: 406 / 329,358.14 bbl / $2,223,458,394 | N3 on Atlas: identical for all 8 categories | ✔ |
| Fatalities/injuries by group | Other worker 6/7, Public 6/5, Contractor 3/32, Employee 1/2 | N4 on Atlas: identical | ✔ |
| External corrosion without cathodic protection, by state | TX 7, CA 5, NJ 2, WY 2, AR/IL/MI/PA 1 | N2: identical | ✔ |
| Narratives mentioning "frozen" | 36 (Portfolio 2 Q6) | N9: 36 | ✔ |
| Total cost of all accidents | $4,619,299,360 | Sum of `total_cost_usd`: $4,619,299,360 | ✔ |

## 4. What the Queries Show

| Query | What it demonstrates |
|---|---|
| **N1** One document = whole report | No joins for the most common operation |
| **N2** Filter on a nested cause answer | Queries reach into `cause.answers` directly. The relational version needed 5 tables. |
| **N3** `$group` by category | Aggregation pipeline, equivalent to SQL `GROUP BY` |
| **N4** `$unwind` casualties | Turning an embedded array into rows for analysis |
| **N5** `$exists` on `vehicle_type` | A field present in 11 documents. In the flat file it was a column empty in 6,041 of 6,052 rows. |
| **N6** `$objectToArray` | The data itself shows how many different questions each cause uses (69 for corrosion, 18 for natural force) |
| **N7** Index-backed sort | Same pattern as the relational composite index |
| **N8** Embedded name history | An operator's 2 names in one document, instead of a separate history table |
| **N9** Text search | Same result as PostgreSQL |
| **N10** Geospatial | "Accidents within 25 km of the Cushing hub" using the stored GeoJSON point. The relational design would need PostGIS or manual distance formulas. |

## 5. Relational vs Document for PipeSafe

| Concern | Relational (PostgreSQL) | Document (MongoDB) |
|---|---|---|
| Varying cause questions | Hundreds of NULL columns, or many detail tables | Only the answered fields are stored |
| Read a complete report | Join 11 tables | One read |
| New report format | Schema change and migration | New `schema_version`, same collection |
| Operator renamed | Change 1 row | Old reports keep the name *as reported*; current name in `operators` |
| Correcting a category label | Change 1 lookup row | `updateMany` across every matching document |
| Integrity between entities | Foreign keys enforced by the database | Application's job (no foreign keys) |
| Ad-hoc questions across entities | Any join, any time | Must fit the document shape, or use `$lookup` (slower) |
| Updating several reports together | Multi-row ACID transactions (Portfolio 3) | Single-document writes are atomic; multi-document transactions exist but cost more |
| Location search | Needs the PostGIS extension | Built in (`2dsphere`) |

## 6. Other NoSQL Models

The brief allows a document, key-value, column-family or graph model. A document model was chosen because it matches the shape of the data. The others would fit different PipeSafe needs:

| Model | Example product | Where it would fit PipeSafe |
|---|---|---|
| **Key-value** | Redis | Caching dashboard figures such as "total cost this year", read thousands of times and refreshed nightly, like the materialised view in Portfolio 2 |
| **Column-family** | Cassandra | Streaming pressure and flow readings from pipeline sensors (SCADA): huge volumes of time-stamped writes |
| **Graph** | Neo4j | Root-cause analysis: *operator → facility → equipment → failure → accident* chains, e.g. "which equipment manufacturers appear in repeated failures across operators?" |

## 7. Conclusion

The document model is a better fit than tables for **storing and reading complete, variably-shaped accident reports**. It keeps all 242 cause questions where the relational design kept a few, reads a whole report in one operation, and absorbs format changes without migrations.

The relational model remains better for **enforcing integrity, ad-hoc analysis across entities, and multi-record transactions**.

A realistic PipeSafe design would use both:
- **PostgreSQL** as the system of record for structured, validated data and transactional updates.
- **MongoDB** for the full report archive, including old-format reports, flexible search and location queries.
