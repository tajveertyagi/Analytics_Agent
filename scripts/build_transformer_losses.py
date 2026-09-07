"""Consolidates the 10 monthly "DT EA Report" production files (Jan-Oct'25)
from Production_Data/ into a single cleaned data/transformer_losses.xlsx.

Real-data quirks handled here:
- Column name variants across files (trailing spaces, "DT_Energy " vs "DT Energy")
- Extra columns present in only some files (Month, BP, Street, ...) are dropped
- Junk placeholder values ('-', '!') in numeric columns -> NaN
- Division name casing inconsistency (e.g. "KASNA" vs "Kasna")
- TnD_loss(%) is stored as a fraction (0.0023 = 0.23%), converted to a percent
- Clustered DTs (Cluster_Information != "No Cluster") have unreliable
  individual loss % (consumer energy is metered at the cluster, not the DT),
  so Distribution_Loss_Pct falls back to Cluster_Loss for those rows
- Rows with |loss %| > 100 are kept but flagged as Data_Quality_Flag='Outlier'
  so dashboards can exclude them from KPIs while still showing them in raw data
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "Production_Data")
OUT_PATH = os.path.join(ROOT, "data", "transformer_losses.xlsx")

# filename -> (year, month) -- hardcoded because filename date formats vary
FILE_MONTHS = {
    "DT EA Report - Jan'25.xlsx": (2025, 1),
    "DT EA Report - Feb'25.xlsx": (2025, 2),
    "DT EA Report - Mar'25.xlsx": (2025, 3),
    "DT EA Report - Apr'25.xlsx": (2025, 4),
    "DT EA (With Negative Loss)_May25.xlsx": (2025, 5),
    "DT EA Report - June'25(With Negative Loss).xlsx": (2025, 6),
    "DT EA Report - July'25 (With Negative Loss).xlsx": (2025, 7),
    "DT EA Report - August'25.xlsx": (2025, 8),
    "DT EA Report(negative) - Sept'25.xlsx": (2025, 9),
    "DT EA Report - October'25 (Including Negative Loss).xlsx": (2025, 10),
}

CANONICAL_COLUMNS = [
    "DT_Meter", "GIS_ID", "Cluster_Information", "Consumer_Count", "DT_Energy",
    "Consumer_Energy", "Units_Loss", "TnD_loss(%)", "Individual_loss_range",
    "Cluster_Loss", "Cluster_Loss_Range", "Feeder_Name", "Substation_Names",
    "Division", "Feeder_type", "DT_type", "Site_Remarks",
]

NUMERIC_COLS = ["Consumer_Count", "DT_Energy", "Consumer_Energy", "Units_Loss", "TnD_loss(%)", "Cluster_Loss"]

DIVISION_CANONICAL = {
    "KASNA": "Kasna", "KASNA ": "Kasna",
    "URBAN-I": "Urban-I", "URBAN-II": "Urban-II",
    "SURAJPUR-I": "Surajpur-I", "SURAJPUR-II": "Surajpur-II",
    "GREATER NOIDA WEST": "Greater Noida West",
}

# DT_type / Feeder_type are capitalized inconsistently across monthly files
# (e.g. "AGRICULTURAL" vs "Agricultural", "Domestic-Urban*" with a stray
# trailing asterisk) -- normalize both to one canonical spelling per category.
CATEGORY_CANONICAL = {
    "AGRICULTURAL": "Agricultural",
    "COMMERCIAL": "Commercial",
    "DOMESTIC-RURAL": "Domestic-Rural",
    "DOMESTIC-URBAN": "Domestic-Urban",
    "INDUSTRIAL": "Industrial",
    "INSTITUTIONAL": "Institutional",
    "PUMP": "Pump",
    "STREET LIGHT": "Street Light",
    "TEMPORARY": "Temporary",
    "CAPTIVE": "Captive",
    "CAPTIVE FEEDER": "Captive",
    "RURAL": "Rural",
    "RURAL URBAN": "Rural Urban",
    "URBAN": "Urban",
}


def _canonical_category(value) -> object:
    if not isinstance(value, str):
        return value
    key = value.strip().rstrip("*").upper()
    return CATEGORY_CANONICAL.get(key, value.strip())


def _load_one(filename: str) -> pd.DataFrame:
    year, month = FILE_MONTHS[filename]
    path = os.path.join(SRC_DIR, filename)
    df = pd.read_excel(path, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={"DT Energy": "DT_Energy"})  # June'25 variant

    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{filename}: missing expected columns {missing}")
    df = df[CANONICAL_COLUMNS].copy()

    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Division"] = df["Division"].astype(str).str.strip()
    df["Division"] = df["Division"].apply(lambda d: DIVISION_CANONICAL.get(d.upper(), d))
    df["DT_type"] = df["DT_type"].apply(_canonical_category)
    df["Feeder_type"] = df["Feeder_type"].apply(_canonical_category)

    df["Date"] = pd.Timestamp(year=year, month=month, day=1)
    return df


def build() -> pd.DataFrame:
    frames = [_load_one(f) for f in FILE_MONTHS]
    df = pd.concat(frames, ignore_index=True)

    df["Is_Clustered"] = df["Cluster_Information"].astype(str).str.strip() != "No Cluster"

    loss_pct_individual = df["TnD_loss(%)"] * 100
    loss_pct_cluster = df["Cluster_Loss"] * 100
    df["Distribution_Loss_Pct"] = np.where(df["Is_Clustered"], loss_pct_cluster, loss_pct_individual)
    # a handful of clustered rows have no Cluster_Loss either -- fall back to individual
    df["Distribution_Loss_Pct"] = df["Distribution_Loss_Pct"].fillna(loss_pct_individual)

    # Consumer_Energy == 0 or missing (while DT_Energy > 0) isn't a measured
    # 100% loss -- it means no billing/meter reading was captured for that
    # DT that month. Flag separately so aggregates don't mistake a metering
    # gap for genuine extreme loss.
    df["Is_Unbilled"] = df["DT_Energy"].fillna(0).gt(0) & (
        df["Consumer_Energy"].isna() | df["Consumer_Energy"].eq(0)
    )

    df["Data_Quality_Flag"] = np.select(
        [df["Is_Unbilled"], df["Distribution_Loss_Pct"].abs() > 100],
        ["Unbilled", "Outlier"],
        default="OK",
    )

    df = df.rename(columns={
        "DT_Meter": "Transformer_ID",
        "DT_Energy": "Energy_Input_kWh",
        "Consumer_Energy": "Energy_Billed_kWh",
        "Units_Loss": "Units_Loss_kWh",
        "Feeder_type": "Feeder_Type",
        "Individual_loss_range": "Loss_Range",
    })

    df["Area_Type"] = df["Feeder_Type"].map(
        lambda t: "Rural" if isinstance(t, str) and "RURAL" in t.upper() else "Urban"
    )

    # Free-text columns occasionally have a stray numeric cell in the source
    # spreadsheets (e.g. a bucket label column with one row typed as a
    # number), which gives pandas a mixed-type "object" column that Parquet
    # (unlike Excel) refuses to write. Force these to plain strings so the
    # downstream Parquet cache (see backend/app/data_cache.py) doesn't choke.
    for col in ["GIS_ID", "Loss_Range", "Cluster_Information", "Cluster_Loss_Range",
                "Substation_Names", "Feeder_Name", "Site_Remarks"]:
        df[col] = df[col].apply(lambda v: v if pd.isna(v) else str(v))

    ordered = [
        "Date", "Division", "Substation_Names", "Feeder_Name", "Transformer_ID", "GIS_ID",
        "DT_type", "Feeder_Type", "Area_Type", "Consumer_Count",
        "Energy_Input_kWh", "Energy_Billed_kWh", "Units_Loss_kWh", "Distribution_Loss_Pct",
        "Loss_Range", "Is_Clustered", "Cluster_Information", "Cluster_Loss_Range",
        "Is_Unbilled", "Data_Quality_Flag", "Site_Remarks",
    ]
    return df[ordered]


if __name__ == "__main__":
    result = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    result.to_excel(OUT_PATH, index=False)
    print(f"transformer_losses.xlsx: {len(result)} rows, {result['Division'].nunique()} divisions, "
          f"{result['Feeder_Name'].nunique()} feeders, {result['Transformer_ID'].nunique()} transformers")
    print(f"Date range: {result['Date'].min().date()} to {result['Date'].max().date()}")
    print(f"Outlier rows flagged: {(result['Data_Quality_Flag'] == 'Outlier').sum()} "
          f"({100*(result['Data_Quality_Flag']=='Outlier').mean():.2f}%)")
    print(f"Unbilled rows flagged: {(result['Data_Quality_Flag'] == 'Unbilled').sum()} "
          f"({100*(result['Data_Quality_Flag']=='Unbilled').mean():.2f}%)")
    print(f"Written to: {OUT_PATH}")
