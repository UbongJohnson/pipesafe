"""
Offline test of the Portfolio 4 queries using mongomock, an in-memory
implementation of MongoDB's query and aggregation engine. No MongoDB server
is needed. Used to check that every query returns the right answer before
running it on MongoDB Atlas.

Usage: python scripts/test_with_mongomock.py data/
Writes results/query_results_mongomock.txt
"""
import json, os, sys
from datetime import datetime
import mongomock
from run_queries import run_all

folder = sys.argv[1]
db = mongomock.MongoClient()["pipesafe"]
for line in open(os.path.join(folder, "accidents.jsonl"), encoding="utf-8"):
    d = json.loads(line)
    d["accident_datetime"] = datetime.fromisoformat(d["accident_datetime"])
    d["report"]["received"] = datetime.fromisoformat(d["report"]["received"])
    db.accidents.insert_one(d)
for line in open(os.path.join(folder, "operators.jsonl"), encoding="utf-8"):
    db.operators.insert_one(json.loads(line))
here = os.path.dirname(os.path.abspath(__file__))
run_all(db, os.path.join(os.path.dirname(here), "results", "query_results_mongomock.txt"))
