"""
Checks every accident document against the rules of the MongoDB schema
validator in load_mongodb.py. Useful when testing on a server that does not
enforce validators.

Usage: python scripts/check_documents.py data/accidents.jsonl
"""
import json, sys

problems = 0
for n, line in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    d = json.loads(line)
    errors = []
    for field in ["_id", "schema_version", "report", "accident_datetime", "operator", "location", "release", "cause"]:
        if field not in d:
            errors.append(f"missing {field}")
    if not isinstance(d.get("_id"), int): errors.append("_id not an integer")
    if not isinstance(d.get("schema_version"), int): errors.append("schema_version not an integer")
    op = d.get("operator", {})
    if "id" not in op or "name" not in op: errors.append("operator missing id/name")
    rel = d.get("release", {})
    for f in ["unintentional_bbls", "recovered_bbls"]:
        v = rel.get(f)
        if not isinstance(v, float) or v < 0: errors.append(f"release.{f} not a non-negative double")
    cause = d.get("cause", {})
    if "category" not in cause or "detail" not in cause: errors.append("cause missing category/detail")
    tc = d.get("total_cost_usd")
    if tc is not None and (not isinstance(tc, float) or tc < 0): errors.append("total_cost_usd not a non-negative double")
    if errors:
        problems += 1
        if problems <= 5:
            print(f"document {d.get('_id')}: {errors}")
print(f"checked {n} documents, {problems} with problems")
