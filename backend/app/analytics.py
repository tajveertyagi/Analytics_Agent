"""Pure pandas analytics functions over the transformer-loss (real production
data) and theft-case (synthetic placeholder) datasets. No Streamlit or LLM
imports here so these are reused identically by the Dashboard pages and the
chatbot tools, keeping numbers consistent everywhere.

Losses schema: Date, Division, Substation_Names, Feeder_Name, Transformer_ID,
GIS_ID, DT_type, Feeder_Type, Area_Type, Consumer_Count, Energy_Input_kWh,
Energy_Billed_kWh, Units_Loss_kWh, Distribution_Loss_Pct, Loss_Range,
Is_Clustered, Cluster_Information, Cluster_Loss_Range, Data_Quality_Flag,
Site_Remarks.

Theft schema: Case_ID, Date, Division, Feeder_Name, Area_Type, Theft_Type,
Units_Stolen_kWh, Fine_Amount_INR, Case_Status, FIR_Filed.
"""
from typing import Optional

import pandas as pd


def filter_df(
    df: pd.DataFrame,
    division: Optional[str] = None,
    feeder_name: Optional[str] = None,
    substation_name: Optional[str] = None,
    area_type: Optional[str] = None,
    dt_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    out = df
    if division:
        out = out[out["Division"] == division]
    if feeder_name:
        out = out[out["Feeder_Name"] == feeder_name]
    if substation_name and "Substation_Names" in out.columns:
        out = out[out["Substation_Names"] == substation_name]
    if area_type and "Area_Type" in out.columns:
        out = out[out["Area_Type"] == area_type]
    if dt_type and "DT_type" in out.columns:
        out = out[out["DT_type"] == dt_type]
    if date_from:
        out = out[out["Date"] >= pd.to_datetime(date_from)]
    if date_to:
        out = out[out["Date"] <= pd.to_datetime(date_to)]
    return out


def _clean_losses(losses: pd.DataFrame) -> pd.DataFrame:
    """Excludes rows flagged as data-quality outliers (|loss %| > 100 from a
    near-zero energy denominator) or unbilled (no consumer meter reading
    captured that month, not a genuine measured loss) from aggregate loss
    calculations."""
    if "Data_Quality_Flag" in losses.columns:
        return losses[losses["Data_Quality_Flag"] == "OK"]
    return losses


def kpi_summary(losses: pd.DataFrame, theft: pd.DataFrame) -> dict:
    clean = _clean_losses(losses)
    total_fine = theft["Fine_Amount_INR"].sum()
    recovered_fine = theft.loc[theft["Case_Status"] == "Penalty Recovered", "Fine_Amount_INR"].sum()
    return {
        "avg_loss_pct": round(clean["Distribution_Loss_Pct"].mean(), 2) if len(clean) else None,
        "total_energy_input_mwh": round(losses["Energy_Input_kWh"].sum() / 1000, 1),
        "total_energy_billed_mwh": round(losses["Energy_Billed_kWh"].sum() / 1000, 1),
        "outlier_rows": int((losses.get("Data_Quality_Flag") == "Outlier").sum()) if "Data_Quality_Flag" in losses.columns else 0,
        "unbilled_rows": int((losses.get("Data_Quality_Flag") == "Unbilled").sum()) if "Data_Quality_Flag" in losses.columns else 0,
        "total_theft_cases": int(len(theft)),
        "total_units_stolen_mwh": round(theft["Units_Stolen_kWh"].sum() / 1000, 1),
        "total_fine_assessed_inr": float(round(total_fine, 0)),
        "total_fine_recovered_inr": float(round(recovered_fine, 0)),
        "total_fine_outstanding_inr": float(round(total_fine - recovered_fine, 0)),
        "recovery_rate_pct": round(100 * recovered_fine / total_fine, 1) if total_fine else 0.0,
    }


def loss_trend(losses: pd.DataFrame, freq: str = "M", group_by: Optional[str] = None) -> pd.DataFrame:
    df = _clean_losses(losses).copy()
    df["Period"] = df["Date"].dt.to_period(freq).dt.to_timestamp()
    keys = ["Period"] + ([group_by] if group_by else [])
    out = df.groupby(keys, as_index=False)["Distribution_Loss_Pct"].mean()
    out = out.rename(columns={"Period": "Date"})
    return out.sort_values("Date")


def top_loss_feeders(losses: pd.DataFrame, n: int = 10, ascending: bool = False) -> pd.DataFrame:
    clean = _clean_losses(losses)
    out = (
        clean.groupby(["Feeder_Name", "Division"], as_index=False)["Distribution_Loss_Pct"]
        .mean()
        .rename(columns={"Distribution_Loss_Pct": "Avg_Loss_Pct"})
    )
    out["Avg_Loss_Pct"] = out["Avg_Loss_Pct"].round(2)
    return out.sort_values("Avg_Loss_Pct", ascending=ascending).head(n).reset_index(drop=True)


def top_loss_substations(losses: pd.DataFrame, n: int = 10, ascending: bool = False) -> pd.DataFrame:
    clean = _clean_losses(losses)
    out = (
        clean.groupby(["Substation_Names", "Division"], as_index=False)["Distribution_Loss_Pct"]
        .mean()
        .rename(columns={"Distribution_Loss_Pct": "Avg_Loss_Pct"})
    )
    out["Avg_Loss_Pct"] = out["Avg_Loss_Pct"].round(2)
    return out.sort_values("Avg_Loss_Pct", ascending=ascending).head(n).reset_index(drop=True)


def loss_by_division(losses: pd.DataFrame) -> pd.DataFrame:
    clean = _clean_losses(losses)
    out = clean.groupby("Division", as_index=False)["Distribution_Loss_Pct"].mean()
    out["Distribution_Loss_Pct"] = out["Distribution_Loss_Pct"].round(2)
    return out.sort_values("Distribution_Loss_Pct", ascending=False).reset_index(drop=True)


def loss_by_dt_type(losses: pd.DataFrame) -> pd.DataFrame:
    clean = _clean_losses(losses)
    out = clean.groupby("DT_type", as_index=False)["Distribution_Loss_Pct"].mean()
    out["Distribution_Loss_Pct"] = out["Distribution_Loss_Pct"].round(2)
    return out.sort_values("Distribution_Loss_Pct", ascending=False).reset_index(drop=True)


def theft_trend(theft: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    df = theft.copy()
    df["Period"] = df["Date"].dt.to_period(freq).dt.to_timestamp()
    out = df.groupby("Period", as_index=False).agg(
        Case_Count=("Case_ID", "count"),
        Units_Stolen_kWh=("Units_Stolen_kWh", "sum"),
        Fine_Amount_INR=("Fine_Amount_INR", "sum"),
    )
    return out.rename(columns={"Period": "Date"}).sort_values("Date")


def theft_by_type(theft: pd.DataFrame) -> pd.DataFrame:
    out = theft.groupby("Theft_Type", as_index=False).agg(
        Case_Count=("Case_ID", "count"),
        Units_Stolen_kWh=("Units_Stolen_kWh", "sum"),
        Fine_Amount_INR=("Fine_Amount_INR", "sum"),
    )
    out["Pct_of_Total_Cases"] = round(100 * out["Case_Count"] / out["Case_Count"].sum(), 1)
    return out.sort_values("Case_Count", ascending=False).reset_index(drop=True)


def theft_by_status(theft: pd.DataFrame) -> pd.DataFrame:
    out = theft.groupby("Case_Status", as_index=False).agg(
        Case_Count=("Case_ID", "count"),
        Fine_Amount_INR=("Fine_Amount_INR", "sum"),
    )
    return out.sort_values("Case_Count", ascending=False).reset_index(drop=True)


def top_theft_feeders(theft: pd.DataFrame, n: int = 10, metric: str = "Case_Count") -> pd.DataFrame:
    out = theft.groupby(["Feeder_Name", "Division"], as_index=False).agg(
        Case_Count=("Case_ID", "count"),
        Units_Stolen_kWh=("Units_Stolen_kWh", "sum"),
        Fine_Amount_INR=("Fine_Amount_INR", "sum"),
    )
    return out.sort_values(metric, ascending=False).head(n).reset_index(drop=True)


def loss_vs_theft_correlation(losses: pd.DataFrame, theft: pd.DataFrame) -> dict:
    """Monthly-per-feeder join of avg loss % vs theft case count/units stolen."""
    l = _clean_losses(losses).copy()
    l["Period"] = l["Date"].dt.to_period("M").dt.to_timestamp()
    l_agg = l.groupby(["Feeder_Name", "Period"], as_index=False)["Distribution_Loss_Pct"].mean()

    t = theft.copy()
    t["Period"] = t["Date"].dt.to_period("M").dt.to_timestamp()
    t_agg = t.groupby(["Feeder_Name", "Period"], as_index=False).agg(
        Case_Count=("Case_ID", "count"),
        Units_Stolen_kWh=("Units_Stolen_kWh", "sum"),
    )

    merged = pd.merge(l_agg, t_agg, on=["Feeder_Name", "Period"], how="inner").fillna(
        {"Case_Count": 0, "Units_Stolen_kWh": 0}
    )
    corr_cases = merged["Distribution_Loss_Pct"].corr(merged["Case_Count"])
    corr_units = merged["Distribution_Loss_Pct"].corr(merged["Units_Stolen_kWh"])
    return {
        "data": merged,
        "correlation_loss_vs_case_count": round(float(corr_cases), 3) if pd.notna(corr_cases) else None,
        "correlation_loss_vs_units_stolen": round(float(corr_units), 3) if pd.notna(corr_units) else None,
    }


def previous_period_range(date_from, date_to) -> tuple:
    """Given a date range, return the immediately preceding range of equal length."""
    start = pd.to_datetime(date_from)
    end = pd.to_datetime(date_to)
    length = end - start
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - length
    return prev_start.date(), prev_end.date()


def aggregate_metric(
    df: pd.DataFrame,
    metric: str,
    agg: str = "sum",
    group_by: Optional[list] = None,
) -> pd.DataFrame:
    """Generic fallback aggregation: used by the chatbot when a question
    doesn't map cleanly onto one of the specialized functions above.
    """
    if group_by:
        out = df.groupby(group_by, as_index=False)[metric].agg(agg)
    else:
        out = pd.DataFrame({metric: [df[metric].agg(agg)]})
    return out
