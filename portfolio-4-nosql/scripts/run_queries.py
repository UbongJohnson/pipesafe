"""
Runs the Portfolio 4 MongoDB queries (the same ones as queries.js) and saves
the output to a results file (default: results/query_results.txt).

Usage:
    python scripts/run_queries.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/" [output file]
"""
import json, os, sys
from pymongo import MongoClient
from pymongo.errors import OperationFailure

HERE = os.path.dirname(os.path.abspath(__file__))
lines = []
db = None


def out(text=""):
    print(text)
    lines.append(str(text))


def show(n, title, fn, note=""):
    out("=" * 78)
    out(f"N{n}. {title}")
    if note:
        out(note)
    out("-" * 78)
    try:
        result = fn()
        if isinstance(result, list):
            for r in result:
                out(json.dumps(r, default=str))
        else:
            out(json.dumps(result, default=str, indent=1))
    except OperationFailure as e:
        out(f"NOT SUPPORTED on this server ({e.code}): {str(e)[:120]}")
    except NotImplementedError as e:          # raised by mongomock (offline testing)
        out(f"NOT SUPPORTED by the test engine: {e}")
    out()


def run_all(database, out_path):
    global db
    db = database
    lines.clear()
    _queries()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("saved to", out_path)


def _queries():
    # N1. The whole accident in ONE read (relational: about 11 tables joined)
    show(1, "Complete record of accident 20170094 in one read",
         lambda: db.accidents.find_one({"_id": 20170094}, {"narrative": 0}),
         "Operator, location, commodity, release, casualties, costs and cause answers\n"
         "all come back together. The relational model joins about 11 tables for this.")

    # N2. External corrosion with no cathodic protection, by state
    show(2, "External corrosion accidents with no cathodic protection, by state",
         lambda: list(db.accidents.aggregate([
             {"$match": {"cause.detail": "EXTERNAL CORROSION",
                         "cause.answers.under_cathodic_protection_ind": False}},
             {"$group": {"_id": "$location.state", "accidents": {"$sum": 1}}},
             {"$sort": {"accidents": -1, "_id": 1}}])),
         "Same question as Portfolio 2 Q7 (which needed 5 tables joined).")

    # N3. Accidents and total cost by cause category
    show(3, "Accidents, barrels released and total cost by cause category",
         lambda: list(db.accidents.aggregate([
             {"$group": {"_id": "$cause.category", "accidents": {"$sum": 1},
                         "bbl_released": {"$sum": "$release.unintentional_bbls"},
                         "total_cost_usd": {"$sum": "$total_cost_usd"}}},
             {"$sort": {"total_cost_usd": -1}}])))

    # N4. Casualties by person group ($unwind the embedded array)
    show(4, "Fatalities and injuries by person group",
         lambda: list(db.accidents.aggregate([
             {"$unwind": "$casualties"},
             {"$group": {"_id": "$casualties.group",
                         "accidents": {"$sum": 1},
                         "fatalities": {"$sum": "$casualties.fatalities"},
                         "injuries": {"$sum": "$casualties.injuries"}}},
             {"$sort": {"fatalities": -1, "injuries": -1}}])),
         "Casualties are an array inside each accident; $unwind turns them into rows.")

    # N5. Flexible schema: query a field that only some documents have
    show(5, "Vehicle-damage accidents: type of vehicle involved",
         lambda: list(db.accidents.aggregate([
             {"$match": {"cause.answers.vehicle_type": {"$exists": True}}},
             {"$group": {"_id": "$cause.answers.vehicle_type", "accidents": {"$sum": 1}}},
             {"$sort": {"accidents": -1}}])),
         "'vehicle_type' exists in only 11 of 6,052 documents. In the flat file it is a\n"
         "column that is empty in 6,041 rows; here it simply appears where it applies.")

    # N6. Which questions were answered, per cause category
    show(6, "How many different cause questions each category actually uses",
         lambda: list(db.accidents.aggregate([
             {"$project": {"category": "$cause.category",
                           "fields": {"$objectToArray": "$cause.answers"}}},
             {"$unwind": "$fields"},
             {"$group": {"_id": {"category": "$category", "field": "$fields.k"}}},
             {"$group": {"_id": "$_id.category", "distinct_fields": {"$sum": 1}}},
             {"$sort": {"distinct_fields": -1}}])),
         "Each cause category has its own set of questions: the variable structure\n"
         "that makes a document model a good fit.")

    # N7. One operator's recent accidents (uses the operator + date index)
    show(7, "Five most recent accidents for operator 31684 (Phillips 66 Pipeline)",
         lambda: list(db.accidents.find(
             {"operator.id": 31684},
             {"_id": 1, "accident_datetime": 1, "report.type": 1, "release.unintentional_bbls": 1})
             .sort("accident_datetime", -1).limit(5)))

    # N8. Operators reported under more than one name
    show(8, "Operators with more than one name (embedded name history)",
         lambda: list(db.operators.find(
             {"name_history.1": {"$exists": True}},
             {"name": 1, "name_history": 1}).sort("_id", 1).limit(5)),
         "52 operators have a second entry in name_history. Shown: the first 5.")

    # N9. Narrative text search
    show(9, "Narratives mentioning frozen equipment",
         lambda: db.accidents.count_documents({"narrative": {"$regex": "frozen", "$options": "i"}}),
         "Same question as Portfolio 2 Q6 (PostgreSQL returned 36 rows).")

    # N10. Geospatial: accidents within 25 km of the Cushing, Oklahoma oil hub
    show(10, "Accidents within 25 km of Cushing, Oklahoma (pipeline hub)",
         lambda: db.accidents.count_documents({"location.geo": {"$geoWithin": {
             "$centerSphere": [[-96.7670, 35.9851], 25 / 6378.1]}}}),
         "Uses the GeoJSON point stored in each document (needs MongoDB / Atlas).")

if __name__ == "__main__":
    run_all(MongoClient(sys.argv[1])["pipesafe"],
            sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(HERE), "results", "query_results.txt"))
