"""
Builds MongoDB documents from the raw PHMSA file.

One document per accident, with everything about it embedded: operator
snapshot, location (with a GeoJSON point), commodity, release, casualties,
costs, and a cause section that keeps EVERY cause-specific answer the operator
gave. These are the answers from the 213 sparse columns that the relational
design (Portfolio 1) only partly kept. Empty answers are left out instead of
stored as NULL, so each document only has the fields that apply to it.

Also builds one document per operator, with its name history.

Usage:
    python scripts/build_documents.py path/to/accident_hazardous_liquid_jan2010_present.txt data/
Writes data/accidents.jsonl and data/operators.jsonl
"""
import json, os, re, sys
import numpy as np
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
def read_phmsa(file):
    """Read the PHMSA file whether it is saved as UTF-8 or as Windows-1252
    (the older Windows text format; also what Excel uses when re-saving)."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            data = pd.read_csv(file, sep="\t", dtype=str, encoding=enc, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    data.columns = data.columns.str.strip()
    if "REPORT_NUMBER" not in data.columns:
        raise SystemExit("This does not look like the PHMSA tab-delimited file: no REPORT_NUMBER column. "
                         "Use the original .txt file from the PHMSA ZIP, not a version saved by Excel as CSV.")
    return data


df = read_phmsa(src)
df = df.replace(r"^\s*$", np.nan, regex=True)
for c in df.columns:
    df[c] = df[c].str.strip()
cols = list(df.columns)

# Column blocks (positions in the PHMSA file, see dataset-analysis.md section 3)
CAUSE_BLOCK = cols[cols.index("CAUSE_DETAILS") + 1: cols.index("COLLECTED_DATA_IND")] + \
              cols[cols.index("EXTRNL_COR_GALVANIC_IND"): cols.index("PREPARER_NAME")]
INSPECTION_BLOCK = cols[cols.index("COLLECTED_DATA_IND"): cols.index("EXTRNL_COR_GALVANIC_IND")]
ENVIRONMENT_BLOCK = cols[cols.index("WILDLIFE_IMPACT_IND"): cols.index("EST_COST_OPER_PAID")]
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def value(v):
    """Convert PHMSA text to a typed value: YES/NO -> bool, digits -> number."""
    if v == "YES":
        return True
    if v == "NO":
        return False
    if NUMBER.match(v):
        return float(v) if "." in v else int(v)
    return v


def answers(row, columns):
    """Only the questions this report actually answered, typed, lower-case names."""
    return {c.lower(): value(row[c]) for c in columns if isinstance(row[c], str)}


def num(v):
    return None if not isinstance(v, str) else float(v)


def ts(v, fmt):
    return pd.to_datetime(v, format=fmt).isoformat()


GROUPS = {"EMP": "EMPLOYEE", "CONTR": "CONTRACTOR", "ER": "EMERGENCY_RESPONDER",
          "WORKER": "OTHER_WORKER", "GP": "PUBLIC"}
COSTS = {"EST_COST_OPER_PAID": "public_property_paid_by_operator",
         "EST_COST_GAS_RELEASED": "commodity_lost",
         "EST_COST_PROP_DAMAGE": "operator_property_damage",
         "EST_COST_EMERGENCY": "emergency_response",
         "EST_COST_ENVIRONMENTAL": "environmental_remediation",
         "EST_COST_OTHER": "other"}

with open(os.path.join(out, "accidents.jsonl"), "w", encoding="utf-8") as f:
    for _, r in df.iterrows():
        county = r.ONSHORE_COUNTY_NAME
        if isinstance(county, str):
            county = re.sub(r"\s+(COUNTY|PARISH|BOROUGH)$", "", county.upper()).strip()
        casualties = []
        for code, label in GROUPS.items():
            fat = int(num(r[f"NUM_{code}_FATALITIES"]) or 0)
            inj = int(num(r[f"NUM_{code}_INJURIES"]) or 0)
            if fat or inj:
                casualties.append({"group": label, "fatalities": fat, "injuries": inj})
        costs = {name: num(r[c]) for c, name in COSTS.items() if isinstance(r[c], str)}
        doc = {
            "_id": int(r.REPORT_NUMBER),
            "schema_version": 2,                      # PHMSA form 7000-1 (2010 onwards)
            "report": {"type": r.REPORT_TYPE,
                       "received": ts(r.REPORT_RECEIVED_DATE, "%m/%d/%Y")},
            "accident_datetime": ts(r.LOCAL_DATETIME, "%m/%d/%Y %H:%M"),
            "operator": {"id": int(r.OPERATOR_ID), "name": r.NAME},
            "facility": r.PIPE_FAC_NAME,
            "location": {
                "on_off_shore": r.ON_OFF_SHORE,
                "state": r.ONSHORE_STATE_ABBREVIATION if isinstance(r.ONSHORE_STATE_ABBREVIATION, str)
                         else r.OFFSHORE_STATE_ABBREVIATION,
                "county": county,
                "city": r.ONSHORE_CITY_NAME,
                "geo": {"type": "Point",
                        "coordinates": [float(r.LOCATION_LONGITUDE), float(r.LOCATION_LATITUDE)]},
            },
            "commodity": {"type": r.COMMODITY_RELEASED_TYPE, "subtype": r.COMMODITY_SUBTYPE},
            "system_part": r.SYSTEM_PART_INVOLVED,
            "item_involved": r.ITEM_INVOLVED,
            "release": {"type": r.RELEASE_TYPE,
                        "unintentional_bbls": num(r.UNINTENTIONAL_RELEASE_BBLS),
                        "intentional_bbls": num(r.INTENTIONAL_RELEASE_BBLS),
                        "recovered_bbls": num(r.RECOVERED_BBLS),
                        "ignited": r.IGNITE_IND == "YES"},
            "casualties": casualties,
            "costs": costs,
            "total_cost_usd": float(sum(v for v in costs.values() if v is not None)),
            "cause": {"category": r.CAUSE, "detail": r.CAUSE_DETAILS,
                      "answers": answers(r, CAUSE_BLOCK)},
            "environment": answers(r, ENVIRONMENT_BLOCK),
            "inspection_history": answers(r, INSPECTION_BLOCK),
            "narrative": r.NARRATIVE,
        }
        # leave out anything empty: missing values, empty lists and empty sub-documents
        def prune(d):
            if isinstance(d, dict):
                return {k: prune(v) for k, v in d.items()
                        if v is not None and not (isinstance(v, float) and np.isnan(v))
                        and v != {} and v != [] and not (isinstance(v, str) and v == "")}
            return d
        doc = prune(prune(doc))
        f.write(json.dumps(doc) + "\n")

# Operators: current name/address + every former name
df["rcv"] = pd.to_datetime(df.REPORT_RECEIVED_DATE, format="%m/%d/%Y")
with open(os.path.join(out, "operators.jsonl"), "w", encoding="utf-8") as f:
    for op_id, g in df.sort_values("rcv").groupby("OPERATOR_ID"):
        latest = g.iloc[-1]
        names = (g.groupby("NAME").rcv.agg(["min", "max"]).sort_values("min").reset_index())
        f.write(json.dumps({
            "_id": int(op_id),
            "name": latest.NAME,
            "address": {k: latest[c] for k, c in [("street", "OPERATOR_STREET_ADDRESS"),
                        ("city", "OPERATOR_CITY_NAME"), ("state_province", "OPERATOR_STATE_ABBREVIATION"),
                        ("postal_code", "OPERATOR_POSTAL_CODE")] if isinstance(latest[c], str)},
            "name_history": [{"name": n.NAME, "first_report": n["min"].date().isoformat(),
                              "last_report": n["max"].date().isoformat()} for _, n in names.iterrows()],
            "accident_count": int(len(g)),
        }) + "\n")
print("accidents:", len(df), "| operators:", df.OPERATOR_ID.nunique())
