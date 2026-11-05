"""
Loads the PipeSafe documents into MongoDB, with a schema validator and indexes.

Usage:
    python scripts/load_mongodb.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/" data/
    (or "mongodb://localhost:27017/" for a local server)
Creates database "pipesafe" with collections "accidents" and "operators".
"""
import json, os, sys
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING, GEOSPHERE
from pymongo.errors import OperationFailure

uri, folder = sys.argv[1], sys.argv[2]
db = MongoClient(uri)["pipesafe"]

# Schema validation: the document model is flexible, but core fields are still required.
accident_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "schema_version", "report", "accident_datetime",
                     "operator", "location", "release", "cause"],
        "properties": {
            "_id": {"bsonType": ["int", "long"], "description": "PHMSA report number"},
            "schema_version": {"bsonType": "int", "minimum": 1},
            "accident_datetime": {"bsonType": "date"},
            "operator": {"bsonType": "object", "required": ["id", "name"]},
            "release": {
                "bsonType": "object",
                "required": ["unintentional_bbls", "recovered_bbls"],
                "properties": {
                    "unintentional_bbls": {"bsonType": "double", "minimum": 0},
                    "recovered_bbls": {"bsonType": "double", "minimum": 0},
                },
            },
            "cause": {"bsonType": "object", "required": ["category", "detail"]},
            "total_cost_usd": {"bsonType": "double", "minimum": 0},
        },
    }
}

for name in ["accidents", "operators"]:
    db.drop_collection(name)
try:
    db.create_collection("accidents", validator=accident_schema, validationLevel="strict")
    print("accidents collection created WITH schema validator")
except OperationFailure as e:
    db.create_collection("accidents")
    print("accidents collection created WITHOUT validator (not supported by this server):", e.code)


def to_dates(doc):
    doc["accident_datetime"] = datetime.fromisoformat(doc["accident_datetime"])
    doc["report"]["received"] = datetime.fromisoformat(doc["report"]["received"])
    return doc


docs = [to_dates(json.loads(l)) for l in open(os.path.join(folder, "accidents.jsonl"), encoding="utf-8")]
for i in range(0, len(docs), 1000):
    db.accidents.insert_many(docs[i:i + 1000], ordered=False)
ops = [json.loads(l) for l in open(os.path.join(folder, "operators.jsonl"), encoding="utf-8")]
db.operators.insert_many(ops)
print("loaded:", db.accidents.count_documents({}), "accidents,", db.operators.count_documents({}), "operators")

indexes = [
    ("operator + date", [("operator.id", ASCENDING), ("accident_datetime", DESCENDING)]),
    ("state + date", [("location.state", ASCENDING), ("accident_datetime", DESCENDING)]),
    ("cause", [("cause.category", ASCENDING), ("cause.detail", ASCENDING)]),
    ("total cost", [("total_cost_usd", DESCENDING)]),
    ("location (2dsphere)", [("location.geo", GEOSPHERE)]),
]
for label, keys in indexes:
    try:
        db.accidents.create_index(keys)
        print("index created:", label)
    except OperationFailure as e:
        print("index NOT supported on this server:", label, "-", e.code)
