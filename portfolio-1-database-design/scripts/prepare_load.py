"""
Transforms the flat PHMSA file into one CSV per normalised table.

Usage:
    python scripts/prepare_load.py path/to/accident_hazardous_liquid_jan2010_present.txt load/
Then run sql/02_load_data.sql from the folder that contains load/.
"""
import sys, os
import numpy as np
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
df = pd.read_csv(src, sep="\t", dtype=str, encoding="utf-8", low_memory=False)
df = df.replace(r"^\s*$", np.nan, regex=True)
for c in df.columns:                                   # trim stray spaces
    df[c] = df[c].str.strip()

num = lambda s: pd.to_numeric(s, errors="coerce")
yesno = lambda s: s.map({"YES": True, "NO": False})
df["acc_dt"] = pd.to_datetime(df.LOCAL_DATETIME, format="%m/%d/%Y %H:%M")
df["rcv_dt"] = pd.to_datetime(df.REPORT_RECEIVED_DATE, format="%m/%d/%Y")

def save(frame, name):
    frame.to_csv(os.path.join(out, f"{name}.csv"), index=False)
    print(f"{name:28s}{len(frame):>7,} rows")

def lookup(series, id_col, name_col):
    vals = sorted(series.dropna().unique())
    return pd.DataFrame({id_col: range(1, len(vals) + 1), name_col: vals})

# ---- operator: name/address from the most recent report ----------------
latest = df.sort_values("rcv_dt").groupby("OPERATOR_ID").tail(1)
operator = pd.DataFrame({
    "operator_id": latest.OPERATOR_ID.astype(int), "operator_name": latest.NAME,
    "street_address": latest.OPERATOR_STREET_ADDRESS, "city": latest.OPERATOR_CITY_NAME,
    "state_province": latest.OPERATOR_STATE_ABBREVIATION, "postal_code": latest.OPERATOR_POSTAL_CODE,
}).sort_values("operator_id")
save(operator, "operator")

hist = (df.groupby(["OPERATOR_ID", "NAME"]).rcv_dt.agg(["min", "max"]).reset_index()
          .rename(columns={"OPERATOR_ID": "operator_id", "NAME": "operator_name",
                           "min": "first_report_date", "max": "last_report_date"}))
hist["first_report_date"] = hist.first_report_date.dt.date
hist["last_report_date"] = hist.last_report_date.dt.date
save(hist, "operator_name_history")

# ---- facility ------------------------------------------------------------
fac = (df.dropna(subset=["PIPE_FAC_NAME"])[["OPERATOR_ID", "PIPE_FAC_NAME"]]
         .drop_duplicates().sort_values(["OPERATOR_ID", "PIPE_FAC_NAME"]).reset_index(drop=True))
fac.insert(0, "facility_id", range(1, len(fac) + 1))
fac.columns = ["facility_id", "operator_id", "facility_name"]
save(fac, "facility")
df = df.merge(fac, how="left", left_on=["OPERATOR_ID", "PIPE_FAC_NAME"],
              right_on=["operator_id", "facility_name"])

# ---- state and county ----------------------------------------------------
STATES = {  # code: (name, U.S. Census region)
 "AK":("Alaska","WEST"),"AL":("Alabama","SOUTH"),"AR":("Arkansas","SOUTH"),"AZ":("Arizona","WEST"),
 "CA":("California","WEST"),"CO":("Colorado","WEST"),"CT":("Connecticut","NORTHEAST"),"DE":("Delaware","SOUTH"),
 "FL":("Florida","SOUTH"),"GA":("Georgia","SOUTH"),"HI":("Hawaii","WEST"),"IA":("Iowa","MIDWEST"),
 "ID":("Idaho","WEST"),"IL":("Illinois","MIDWEST"),"IN":("Indiana","MIDWEST"),"KS":("Kansas","MIDWEST"),
 "KY":("Kentucky","SOUTH"),"LA":("Louisiana","SOUTH"),"MA":("Massachusetts","NORTHEAST"),"MD":("Maryland","SOUTH"),
 "ME":("Maine","NORTHEAST"),"MI":("Michigan","MIDWEST"),"MN":("Minnesota","MIDWEST"),"MO":("Missouri","MIDWEST"),
 "MS":("Mississippi","SOUTH"),"MT":("Montana","WEST"),"NC":("North Carolina","SOUTH"),"ND":("North Dakota","MIDWEST"),
 "NE":("Nebraska","MIDWEST"),"NH":("New Hampshire","NORTHEAST"),"NJ":("New Jersey","NORTHEAST"),"NM":("New Mexico","WEST"),
 "NV":("Nevada","WEST"),"NY":("New York","NORTHEAST"),"OH":("Ohio","MIDWEST"),"OK":("Oklahoma","SOUTH"),
 "OR":("Oregon","WEST"),"PA":("Pennsylvania","NORTHEAST"),"RI":("Rhode Island","NORTHEAST"),"SC":("South Carolina","SOUTH"),
 "SD":("South Dakota","MIDWEST"),"TN":("Tennessee","SOUTH"),"TX":("Texas","SOUTH"),"UT":("Utah","WEST"),
 "VA":("Virginia","SOUTH"),"VT":("Vermont","NORTHEAST"),"WA":("Washington","WEST"),"WI":("Wisconsin","MIDWEST"),
 "WV":("West Virginia","SOUTH"),"WY":("Wyoming","WEST"),"DC":("District of Columbia","SOUTH"),
 "PR":("Puerto Rico","TERRITORY"),
}
save(pd.DataFrame([(k, v[0], v[1]) for k, v in sorted(STATES.items())],
                  columns=["state_code", "state_name", "region"]), "state")

df["county_clean"] = (df.ONSHORE_COUNTY_NAME.str.upper()
                        .str.replace(r"\s+(COUNTY|PARISH|BOROUGH)$", "", regex=True).str.strip())
cty = (df.dropna(subset=["ONSHORE_STATE_ABBREVIATION", "county_clean"])
         [["ONSHORE_STATE_ABBREVIATION", "county_clean"]].drop_duplicates()
         .sort_values(["ONSHORE_STATE_ABBREVIATION", "county_clean"]).reset_index(drop=True))
cty.insert(0, "county_id", range(1, len(cty) + 1))
cty.columns = ["county_id", "state_code", "county_name"]
save(cty, "county")
df = df.merge(cty, how="left", left_on=["ONSHORE_STATE_ABBREVIATION", "county_clean"],
              right_on=["state_code", "county_name"])

# ---- lookups ---------------------------------------------------------------
ctype = lookup(df.COMMODITY_RELEASED_TYPE, "commodity_type_id", "type_name"); save(ctype, "commodity_type")
df["subtype_clean"] = df.COMMODITY_SUBTYPE.fillna("NOT SPECIFIED")
csub = (df[["COMMODITY_RELEASED_TYPE", "subtype_clean"]].drop_duplicates()
          .merge(ctype, left_on="COMMODITY_RELEASED_TYPE", right_on="type_name")
          .sort_values(["commodity_type_id", "subtype_clean"]).reset_index(drop=True))
csub["commodity_subtype_id"] = range(1, len(csub) + 1)
save(csub[["commodity_subtype_id", "commodity_type_id", "subtype_clean"]]
         .rename(columns={"subtype_clean": "subtype_name"}), "commodity_subtype")
df = df.merge(csub[["COMMODITY_RELEASED_TYPE", "subtype_clean", "commodity_subtype_id"]],
              on=["COMMODITY_RELEASED_TYPE", "subtype_clean"])

ccat = lookup(df.CAUSE, "cause_category_id", "category_name"); save(ccat, "cause_category")
cdet = (df[["CAUSE", "CAUSE_DETAILS"]].drop_duplicates()
          .merge(ccat, left_on="CAUSE", right_on="category_name")
          .sort_values(["cause_category_id", "CAUSE_DETAILS"]).reset_index(drop=True))
cdet["cause_detail_id"] = range(1, len(cdet) + 1)
save(cdet[["cause_detail_id", "cause_category_id", "CAUSE_DETAILS"]]
         .rename(columns={"CAUSE_DETAILS": "detail_name"}), "cause_detail")
df = df.merge(cdet[["CAUSE", "CAUSE_DETAILS", "cause_detail_id"]], on=["CAUSE", "CAUSE_DETAILS"])

for col, table, idc, namec in [("SYSTEM_PART_INVOLVED", "system_part", "system_part_id", "part_name"),
                               ("ITEM_INVOLVED", "item_involved", "item_involved_id", "item_name"),
                               ("ACCIDENT_IDENTIFIER", "detection_method", "detection_method_id", "method_name")]:
    lk = lookup(df[col], idc, namec); save(lk, table)
    df = df.merge(lk, how="left", left_on=col, right_on=namec)

COSTS = [("EST_COST_OPER_PAID", "Public and non-operator private property damage paid by operator"),
         ("EST_COST_GAS_RELEASED", "Commodity lost"),
         ("EST_COST_PROP_DAMAGE", "Operator's property damage and repairs"),
         ("EST_COST_EMERGENCY", "Emergency response"),
         ("EST_COST_ENVIRONMENTAL", "Environmental remediation"),
         ("EST_COST_OTHER", "Other costs")]
cost_type = pd.DataFrame([(i + 1, c, d) for i, (c, d) in enumerate(COSTS)],
                         columns=["cost_type_id", "cost_code", "description"])
save(cost_type, "cost_type")

# ---- accident ------------------------------------------------------------
iy = num(df.INSTALLATION_YEAR)
acc = pd.DataFrame({
    "report_number": df.REPORT_NUMBER.astype("int64"), "report_type": df.REPORT_TYPE,
    "report_received_date": df.rcv_dt.dt.date, "operator_id": df.OPERATOR_ID.astype(int),
    "facility_id": df.facility_id.astype("Int64"), "segment_name": df.SEGMENT_NAME,
    "on_off_shore": df.ON_OFF_SHORE, "county_id": df.county_id.astype("Int64"),
    "city_name": df.ONSHORE_CITY_NAME.str.upper(),
    "latitude": num(df.LOCATION_LATITUDE).round(6), "longitude": num(df.LOCATION_LONGITUDE).round(6),
    "accident_datetime": df.acc_dt, "time_zone": df.TIME_ZONE,
    "pipe_facility_type": df.PIPE_FACILITY_TYPE, "system_part_id": df.system_part_id,
    "item_involved_id": df.item_involved_id, "installation_year": iy.astype("Int64"),
    "detection_method_id": df.detection_method_id.astype("Int64"),
    "commodity_subtype_id": df.commodity_subtype_id, "release_type": df.RELEASE_TYPE,
    "unintentional_release_bbls": num(df.UNINTENTIONAL_RELEASE_BBLS),
    "intentional_release_bbls": num(df.INTENTIONAL_RELEASE_BBLS),
    "recovered_bbls": num(df.RECOVERED_BBLS).fillna(0),
    "ignited": yesno(df.IGNITE_IND), "exploded": yesno(df.EXPLODE_IND),
    "shutdown_required": yesno(df.SHUTDOWN_DUE_ACCIDENT_IND),
    "public_evacuated": num(df.NUM_PUB_EVACUATED).astype("Int64"),
    "cause_detail_id": df.cause_detail_id, "narrative": df.NARRATIVE,
}).sort_values("report_number")
save(acc, "accident")

off = df[df.ON_OFF_SHORE == "OFFSHORE"]
save(pd.DataFrame({
    "report_number": off.REPORT_NUMBER.astype("int64"), "origin": off.OFF_ACCIDENT_ORIGIN,
    "adjacent_state_code": off.OFFSHORE_STATE_ABBREVIATION,
    "area_name": off.OFF_OCS_AREA.fillna(off.OFF_INSTATE_AREA),
    "block_number": off.OFF_OCS_BLOCK.fillna(off.OFF_INSTATE_BLOCK),
    "water_depth_ft": num(off.OFF_WATER_DEPTH), "ocs_region": off.OCS_TYPE}), "offshore_location")

# ---- casualty (reshape 10 columns into rows) ------------------------------
groups = {"EMP": "EMPLOYEE", "CONTR": "CONTRACTOR", "ER": "EMERGENCY_RESPONDER",
          "WORKER": "OTHER_WORKER", "GP": "PUBLIC"}
rows = []
for code, label in groups.items():
    f = num(df[f"NUM_{code}_FATALITIES"]).fillna(0).astype(int)
    i = num(df[f"NUM_{code}_INJURIES"]).fillna(0).astype(int)
    part = pd.DataFrame({"report_number": df.REPORT_NUMBER.astype("int64"),
                         "person_group": label, "fatalities": f, "injuries": i})
    rows.append(part[(part.fatalities + part.injuries) > 0])
save(pd.concat(rows).sort_values(["report_number", "person_group"]), "casualty")

# ---- accident_cost (reshape 6 columns into rows) --------------------------
rows = []
for _, r in cost_type.iterrows():
    amt = num(df[r.cost_code])
    part = pd.DataFrame({"report_number": df.REPORT_NUMBER.astype("int64"),
                         "cost_type_id": r.cost_type_id, "amount_usd": amt})
    rows.append(part.dropna(subset=["amount_usd"]))
save(pd.concat(rows).sort_values(["report_number", "cost_type_id"]), "accident_cost")

# ---- cause-specific detail tables ------------------------------------------
c = df[df.CAUSE == "CORROSION FAILURE"]
save(pd.DataFrame({"report_number": c.REPORT_NUMBER.astype("int64"),
                   "visual_exam_result": c.VISUAL_EXAM_RESULTS,
                   "under_cathodic_protection": yesno(c.UNDER_CATHODIC_PROTECTION_IND),
                   "externally_coated": yesno(c.EXTERNALLY_COATED),
                   "corrosion_inhibitors_used": yesno(c.CORROSION_INHIBITORS),
                   "prior_damage": c.PRIOR_DAMAGE}), "corrosion_detail")
e = df[df.CAUSE == "EXCAVATION DAMAGE"]
save(pd.DataFrame({"report_number": e.REPORT_NUMBER.astype("int64"),
                   "excavator_type": e.EXCAVATOR_TYPE, "excavator_equipment": e.EXCAVATOR_EQUIPMENT,
                   "work_performed": e.WORK_PERFORMED, "one_call_notified": yesno(e.ONE_CALL_NOTIFIED_IND),
                   "prior_notification": yesno(e.PRIOR_NOTIFICATION_IND),
                   "root_cause_category": e.ROOT_CAUSE_CATEGORY}), "excavation_detail")
o = df[df.CAUSE == "INCORRECT OPERATION"]
flag = lambda s: s.eq("YES")
save(pd.DataFrame({"report_number": o.REPORT_NUMBER.astype("int64"),
                   "activity_category": o.CATEGORY_TYPE,
                   "operator_qualified": yesno(o.OPERATOR_QUALIFICATION_IND),
                   "inadequate_procedure": flag(o.RELATED_INADEQUATE_PROC_IND),
                   "no_procedure": flag(o.RELATED_NO_PROC_IND),
                   "failure_to_follow_procedure": flag(o.RELATED_FAILURE_FOLLOW_IND)}),
     "incorrect_operation_detail")
