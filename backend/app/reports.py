"""Builds a multi-sheet Excel (.xlsx) analytics report for an arbitrary
timeframe (and optional filters), reusing app.analytics so the numbers match
the chatbot and dashboard exactly.

Sheets: a headline Summary plus one sheet per breakdown (loss by division /
DT type, top loss feeders / substations, monthly loss trend, theft by type /
status, monthly theft trend, top theft feeders). Distribution-loss figures
are real production data; theft figures are synthetic placeholder data and
the Summary sheet says so.
"""
import io
import re
from typing import Optional

import pandas as pd

from app import analytics as A

_EMPTY_NOTE = "No rows match the selected timeframe / filters."


def _slug(text: str) -> str:
    text = re.sub(r"\.(xlsx|xls|csv)$", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-") or "report"


def _timeframe_label(
    fl: pd.DataFrame,
    ft: pd.DataFrame,
    date_from: Optional[str],
    date_to: Optional[str],
) -> str:
    if date_from or date_to:
        lo = pd.to_datetime(date_from).strftime("%d %b %Y") if date_from else "start"
        hi = pd.to_datetime(date_to).strftime("%d %b %Y") if date_to else "latest"
        return f"{lo} to {hi}"
    dates = pd.concat([fl["Date"], ft["Date"]]) if len(fl) or len(ft) else pd.Series([], dtype="datetime64[ns]")
    dates = dates.dropna()
    if dates.empty:
        return "all available data"
    return f"{dates.min().strftime('%b %Y')} to {dates.max().strftime('%b %Y')} (all available)"


def _filters_label(**filters) -> str:
    active = {k: v for k, v in filters.items() if v}
    if not active:
        return "none (whole network)"
    return ", ".join(f"{k}={v}" for k, v in active.items())


def _summary_frame(kpi: dict, timeframe: str, filters_label: str) -> pd.DataFrame:
    rows = [
        ("Report", "Sarthi DISCOM Analytics Report"),
        ("Timeframe", timeframe),
        ("Filters", filters_label),
        ("Data note", "Distribution-loss figures are REAL production data. Theft-case figures are SYNTHETIC placeholder data."),
        ("", ""),
        ("Average distribution loss %", kpi.get("avg_loss_pct")),
        ("Total energy input (MWh)", kpi.get("total_energy_input_mwh")),
        ("Total energy billed (MWh)", kpi.get("total_energy_billed_mwh")),
        ("Data-quality: outlier rows excluded", kpi.get("outlier_rows")),
        ("Data-quality: unbilled rows excluded", kpi.get("unbilled_rows")),
        ("", ""),
        ("Total theft cases (synthetic)", kpi.get("total_theft_cases")),
        ("Units stolen (MWh, synthetic)", kpi.get("total_units_stolen_mwh")),
        ("Fine assessed (INR, synthetic)", kpi.get("total_fine_assessed_inr")),
        ("Fine recovered (INR, synthetic)", kpi.get("total_fine_recovered_inr")),
        ("Fine outstanding (INR, synthetic)", kpi.get("total_fine_outstanding_inr")),
        ("Recovery rate % (synthetic)", kpi.get("recovery_rate_pct")),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def build_report(
    losses: pd.DataFrame,
    theft: pd.DataFrame,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    division: Optional[str] = None,
    feeder_name: Optional[str] = None,
    substation_name: Optional[str] = None,
    area_type: Optional[str] = None,
    dt_type: Optional[str] = None,
    title: Optional[str] = None,
) -> tuple[str, str, str, bytes]:
    """Returns (filename, timeframe_label, filters_label, xlsx_bytes)."""
    fl = A.filter_df(
        losses,
        division=division,
        feeder_name=feeder_name,
        substation_name=substation_name,
        area_type=area_type,
        dt_type=dt_type,
        date_from=date_from,
        date_to=date_to,
    )
    ft = A.filter_df(
        theft,
        division=division,
        feeder_name=feeder_name,
        area_type=area_type,
        date_from=date_from,
        date_to=date_to,
    )

    timeframe = _timeframe_label(fl, ft, date_from, date_to)
    filters_label = _filters_label(
        division=division,
        feeder_name=feeder_name,
        substation_name=substation_name,
        area_type=area_type,
        dt_type=dt_type,
    )
    kpi = A.kpi_summary(fl, ft)

    sheets: dict[str, pd.DataFrame] = {
        "Summary": _summary_frame(kpi, timeframe, filters_label),
        "Loss by Division": A.loss_by_division(fl),
        "Loss by DT Type": A.loss_by_dt_type(fl),
        "Top Loss Feeders": A.top_loss_feeders(fl, n=25),
        "Top Loss Substations": A.top_loss_substations(fl, n=25),
        "Loss Trend (Monthly)": A.loss_trend(fl, freq="M"),
        "Theft by Type": A.theft_by_type(ft),
        "Theft by Status": A.theft_by_status(ft),
        "Theft Trend (Monthly)": A.theft_trend(ft),
        "Top Theft Feeders": A.top_theft_feeders(ft, n=25),
    }

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for name, df in sheets.items():
            frame = df if not df.empty else pd.DataFrame({"Note": [_EMPTY_NOTE]})
            frame.to_excel(xl, sheet_name=name[:31], index=False)

    base = _slug(title) if title else "DISCOM-Analytics-Report"
    filename = f"{base}_{_slug(timeframe)}.xlsx"
    return filename, timeframe, filters_label, buf.getvalue()
