"""
Cloud evidence for Portfolio 5: inspects the MongoDB Atlas cluster that holds
the Portfolio 4 data. Every Atlas cluster, including the free M0 tier, is a
3-node replica set spread across availability zones.

Shows:
  * the replica set members and which one is primary
  * a read served with readPreference "secondaryPreferred"
  * the cost of stronger write guarantees: w=1 vs w="majority"

Usage:
    python scripts/atlas_replica_check.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"
Writes results/atlas_replica_check.log
"""
import os, statistics, sys, time
from pymongo import MongoClient, ReadPreference
from pymongo.write_concern import WriteConcern

client = MongoClient(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(HERE), "results", "atlas_replica_check.log")
lines = []


def log(text=""):
    print(text)
    lines.append(str(text))


hello = client.admin.command("hello")
log("Replica set name : " + str(hello.get("setName", "(not a replica set)")))
log("Members          : " + ", ".join(hello.get("hosts", [])))
log("Current primary  : " + str(hello.get("primary")))
log("Server version   : " + client.server_info()["version"])

db = client["pipesafe"]
secondary = db.get_collection("accidents", read_preference=ReadPreference.SECONDARY_PREFERRED)
log(f"Accidents counted via a secondary-preferred read: {secondary.count_documents({})}")

test = db["replication_test"]
test.drop()
for label, wc in [("w=1 (primary only)", WriteConcern(w=1)),
                  ("w='majority' (2 of 3 nodes)", WriteConcern(w="majority"))]:
    coll = test.with_options(write_concern=wc)
    times = []
    for i in range(20):
        t = time.perf_counter()
        coll.insert_one({"n": i, "write_concern": label})
        times.append((time.perf_counter() - t) * 1000)
    log(f"Median insert time with {label}: {statistics.median(times):.1f} ms")
test.drop()

os.makedirs(os.path.dirname(LOG), exist_ok=True)
with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("saved to", LOG)
