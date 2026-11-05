# Portfolio 4: NoSQL and Advanced Data Models

The PipeSafe case study modelled as a **MongoDB document database**. Each accident report becomes one document holding everything about it, including **all 242 cause-specific questions** that the relational design could only partly keep, stored only where they were answered.

Every query answer was cross-checked against PostgreSQL and matches exactly.

## Contents

| File | What it contains |
|---|---|
| `nosql-report.md` | **The write-up:** why a document model fits, the design (embed vs reference), validation, indexes, testing, comparison with the relational model, other NoSQL models |
| `queries.js` | The 10 queries for `mongosh` / the Atlas shell |
| `scripts/build_documents.py` | Turns the raw PHMSA file into accident and operator documents (JSON Lines) |
| `scripts/check_documents.py` | Checks every document against the validator rules |
| `scripts/load_mongodb.py` | Creates the collections with a `$jsonSchema` validator, loads the data, creates 5 indexes |
| `scripts/run_queries.py` | Runs the same 10 queries from Python and saves the output |
| `scripts/test_with_mongomock.py` | Offline test of the queries with no server (mongomock) |
| `data/sample_documents.json` | 4 example documents: valve error, excavation, onshore corrosion, offshore corrosion |
| `results/query_results_ferretdb.txt` | Query output from FerretDB (MongoDB-compatible server) |
| `results/query_results_mongomock.txt` | Query output from mongomock |
| `screenshots/` | Evidence from MongoDB Atlas |

The full document files (`data/accidents.jsonl`, 15 MB) are not committed. Rebuild them with `build_documents.py`.

## How to Run on MongoDB Atlas (free)

1. **Create a free cluster.** Sign up at mongodb.com/atlas and create a free **M0** cluster.
   - Under **Database Access**, add a user with a password.
   - Under **Network Access**, add your IP address.
   - Click **Connect → Drivers** and copy the connection string (`mongodb+srv://…`).
2. **Install the Python packages:**
   ```bash
   pip install pymongo pandas numpy
   ```
3. **Build, check, load and query** (run from this folder):
   ```bash
   python scripts/build_documents.py path/to/accident_hazardous_liquid_jan2010_present.txt data/
   python scripts/check_documents.py data/accidents.jsonl
   python scripts/load_mongodb.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/" data/
   python scripts/run_queries.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/" results/query_results_atlas.txt
   ```
   On Atlas, `load_mongodb.py` should report the collection created **with** the schema validator and all **5** indexes, including `2dsphere`.

4. **Optional:** run `queries.js` in the **mongosh** shell built into Atlas (Data Explorer → Open MongoDB Shell), or paste each query into Compass.

Never commit your connection string or password to GitHub.

## Expected Results

| Query | Expected answer |
|---|---|
| N2 Corrosion, no cathodic protection | TX 7, CA 5, NJ 2, WY 2, AR 1, IL 1, MI 1, PA 1 |
| N3 By cause category | e.g. Material failure: 406 accidents, $2,223,458,394 |
| N4 Casualties | Contractor 3 fatalities / 32 injuries; Public 6 / 5; Other worker 6 / 7; Employee 1 / 2 |
| N6 Questions per cause | Corrosion 69, Equipment 59, Material 42, Excavation 41 … |
| N9 "frozen" | 36 |
| N10 Within 25 km of Cushing, OK | 178 |

## Screenshots to Take

1. Atlas **Collections** view showing one accident document expanded (e.g. `_id: 20260244`, with its `cause.answers`).
2. The **Indexes** tab showing the 5 indexes.
3. The **Validation** tab showing the `$jsonSchema` rules.
4. Output of `run_queries.py`, or the N6 and N10 results in the Atlas shell.
5. **Optional:** try inserting a document without `cause` and screenshot the validation error.
