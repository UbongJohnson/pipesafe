"""
Portfolio 1 - Dataset analysis of the PHMSA Hazardous Liquid Accident data (Jan 2010 - present).

Usage:
    python scripts/data_profile.py path/to/accident_hazardous_liquid_jan2010_present.txt

Prints a profile of the raw file (size, years, missing values, operators,
categories, data-quality checks) and writes data/sample.csv.
"""
import sys
import numpy as np
import pandas as pd

path = sys.argv[1]
df = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8", low_memory=False)
df = df.replace(r"^\s*$", np.nan, regex=True)          # blank strings -> NULL
num = lambda c: pd.to_numeric(df[c], errors="coerce")

print("== 1. Size ==")
print("rows:", len(df), "| columns:", df.shape[1])
print("unique REPORT_NUMBER:", df.REPORT_NUMBER.nunique())
print("REPORT_TYPE:", df.REPORT_TYPE.value_counts().to_dict())

print("\n== 2. Accidents per year ==")
print(df.IYEAR.value_counts().sort_index().to_dict())

print("\n== 3. Missing values (share of columns) ==")
miss = df.isna().mean()
bands = pd.cut(miss, [-0.01, 0, 0.1, 0.5, 0.9, 0.99, 1.0],
               labels=["0%", "0-10%", "10-50%", "50-90%", "90-99%", "99-100%"])
print(bands.value_counts().sort_index().to_dict())
print("completely empty columns:", int((miss == 1).sum()))

print("\n== 4. Operators ==")
names_per_id = df.groupby("OPERATOR_ID").NAME.nunique()
addr_per_id = df.groupby("OPERATOR_ID").OPERATOR_STREET_ADDRESS.nunique()
print("operator IDs:", df.OPERATOR_ID.nunique(), "| distinct names:", df.NAME.nunique())
print("IDs with more than one name:", int((names_per_id > 1).sum()))
print("IDs with more than one address:", int((addr_per_id > 1).sum()))
print("top 5 operators:", df.NAME.value_counts().head(5).to_dict())

print("\n== 5. Categories ==")
for c in ["COMMODITY_RELEASED_TYPE", "COMMODITY_SUBTYPE", "CAUSE", "CAUSE_DETAILS",
          "SYSTEM_PART_INVOLVED", "ON_OFF_SHORE", "ONSHORE_STATE_ABBREVIATION",
          "ONSHORE_COUNTY_NAME", "PIPE_FAC_NAME"]:
    print(f"{c}: {df[c].nunique()} distinct values")
print("CAUSE_DETAILS values linked to more than one CAUSE:",
      int((df.groupby("CAUSE_DETAILS").CAUSE.nunique() > 1).sum()))

print("\n== 6. Data-quality checks ==")
released = num("UNINTENTIONAL_RELEASE_BBLS").fillna(0) + num("INTENTIONAL_RELEASE_BBLS").fillna(0)
print("recovered > released:", int((num("RECOVERED_BBLS") > released).sum()))
cost_cols = ["EST_COST_OPER_PAID", "EST_COST_GAS_RELEASED", "EST_COST_PROP_DAMAGE",
             "EST_COST_EMERGENCY", "EST_COST_ENVIRONMENTAL", "EST_COST_OTHER"]
print("negative costs:", int(sum((num(c) < 0).sum() for c in cost_cols)))
total = sum(num(c).fillna(0) for c in cost_cols)
print("PRPTY equals sum of cost columns:", f"{(abs(total - num('PRPTY')) < 1).mean():.0%}")
acc_dt = pd.to_datetime(df.LOCAL_DATETIME, format="%m/%d/%Y %H:%M", errors="coerce")
print("accident date range:", acc_dt.min(), "to", acc_dt.max())
print("IYEAR differs from accident year:", int((acc_dt.dt.year.astype(str) != df.IYEAR).sum()))
iy = num("INSTALLATION_YEAR")
print("INSTALLATION_YEAR non-numeric values:",
      df.INSTALLATION_YEAR[df.INSTALLATION_YEAR.notna() & iy.isna()].value_counts().to_dict())
county = df.ONSHORE_COUNTY_NAME.dropna()
cleaned = county.str.upper().str.replace(r"\s+(COUNTY|PARISH|BOROUGH)$", "", regex=True).str.strip()
print("county spellings:", county.nunique(), "-> after cleaning:", cleaned.nunique())
print("offshore rows without a state:", int(df.ONSHORE_STATE_ABBREVIATION.isna().sum()))

print("\n== 7. Cause-specific columns are only filled for their own cause ==")
for col, cause in {"INTERNAL_EXTERNAL": "CORROSION FAILURE", "EX_PARTY_TYPE": "EXCAVATION DAMAGE",
                   "NATURAL_FORCE_TYPE": "NATURAL FORCE DAMAGE", "EQ_FAILURE_TYPE": "EQUIPMENT FAILURE",
                   "OPERATION_TYPE": "INCORRECT OPERATION",
                   "OUTSIDE_FORCE_TYPE": "OTHER OUTSIDE FORCE DAMAGE"}.items():
    filled = df[col].notna()
    print(f"{col}: filled {filled.sum()}, all for '{cause}': {(df.CAUSE[filled] == cause).all()}")

# Sample file: core columns only, no personal contact details
core = ["REPORT_NUMBER", "REPORT_TYPE", "IYEAR", "LOCAL_DATETIME", "OPERATOR_ID", "NAME",
        "OPERATOR_STREET_ADDRESS", "OPERATOR_CITY_NAME", "OPERATOR_STATE_ABBREVIATION",
        "PIPE_FAC_NAME", "SYSTEM_PART_INVOLVED", "ON_OFF_SHORE", "ONSHORE_STATE_ABBREVIATION",
        "ONSHORE_COUNTY_NAME", "ONSHORE_CITY_NAME", "LOCATION_LATITUDE", "LOCATION_LONGITUDE",
        "COMMODITY_RELEASED_TYPE", "COMMODITY_SUBTYPE", "UNINTENTIONAL_RELEASE_BBLS",
        "INTENTIONAL_RELEASE_BBLS", "RECOVERED_BBLS", "CAUSE", "CAUSE_DETAILS", "FATAL", "INJURE",
        "EST_COST_PROP_DAMAGE", "EST_COST_EMERGENCY", "EST_COST_ENVIRONMENTAL", "PRPTY"]
df.sort_values("REPORT_NUMBER").groupby("CAUSE").head(4)[core].to_csv("data/sample.csv", index=False)
print("\nwrote data/sample.csv")
