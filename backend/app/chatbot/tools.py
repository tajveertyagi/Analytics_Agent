"""Structured tools exposed to the LLM. The model can only call these fixed,
typed functions (never arbitrary code) -- each wraps app.analytics and
optionally returns a JSON-safe Plotly figure dict for the chat UI to render
alongside the model's explanation. Results are TTL-cached since the same
analytics questions get asked repeatedly across users/sessions.
"""
import json
import threading

import numpy as np
import pandas as pd
from cachetools import TTLCache

from app import analytics as A
from app import charts as C
from app.config import TOOL_CACHE_TTL_SECONDS


def _json_default(o):
    """Safety net: pandas aggregations can leak numpy scalar types (e.g.
    numpy.int64 when a summed column happens to be integer-dtyped), which
    the stdlib json module cannot serialize."""
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _dumps(obj) -> str:
    return json.dumps(obj, default=_json_default)


_COMMON_FILTER_PROPS = {
    "division": {"type": "string", "description": "Filter to a specific Division, e.g. 'Kasna', 'Urban-I', 'Surajpur-II', 'Greater Noida West'."},
    "feeder_name": {"type": "string", "description": "Filter to a specific Feeder_Name."},
    "area_type": {"type": "string", "enum": ["Urban", "Rural"], "description": "Filter to Urban or Rural feeders."},
    "date_from": {"type": "string", "description": "ISO date (YYYY-MM-DD) lower bound, inclusive."},
    "date_to": {"type": "string", "description": "ISO date (YYYY-MM-DD) upper bound, inclusive."},
}

_LOSS_FILTER_PROPS = {
    **_COMMON_FILTER_PROPS,
    "dt_type": {
        "type": "string",
        "description": "Filter to a specific transformer type, e.g. 'Domestic-Rural', 'Domestic-Urban', 'Commercial', 'Industrial', 'Agricultural', 'Institutional', 'Pump', 'Street Light'.",
    },
    "substation_name": {
        "type": "string",
        "description": "Filter to a specific Substation_Names value. Losses-only dimension (not present in theft data).",
    },
}


def _to_records(df: pd.DataFrame, limit: int = 25) -> list:
    return json.loads(df.head(limit).to_json(orient="records", date_format="iso"))


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_kpi_summary",
            "description": "Get headline KPIs: avg distribution loss % (real data), energy input/billed, total theft cases (synthetic placeholder data), units stolen, and fine amounts. Returns three DISTINCT fine figures -- total_fine_assessed_inr (all fines issued, regardless of status), total_fine_recovered_inr (only cases with Case_Status='Penalty Recovered' -- use this for 'how much was recovered'), and total_fine_outstanding_inr (assessed minus recovered). Do not confuse these.",
            "parameters": {"type": "object", "properties": _LOSS_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_loss_trend",
            "description": "Get distribution loss % trend over time (monthly), optionally grouped by Division/Feeder_Name/Substation_Names/DT_type/Feeder_Type. Produces a line chart. Uses real production data.",
            "parameters": {
                "type": "object",
                "properties": {
                    **_LOSS_FILTER_PROPS,
                    "group_by": {"type": "string", "enum": ["Division", "Feeder_Name", "Substation_Names", "DT_type", "Feeder_Type"], "description": "Optional column to split the trend by."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_loss_feeders",
            "description": "Rank INDIVIDUAL FEEDERS by average distribution loss %. Use ONLY for questions that specifically say 'feeder'. Do NOT use this for Substation questions (use get_top_loss_substations), Division questions (use get_loss_by_division), or DT type questions (use get_loss_by_dt_type) -- a feeder's loss is not the same as its substation's or division's average, and a feeder result must never be described as a substation. Produces a bar chart. Uses real production data.",
            "parameters": {
                "type": "object",
                "properties": {
                    **_LOSS_FILTER_PROPS,
                    "n": {"type": "integer", "description": "Number of feeders to return (default 10)."},
                    "ascending": {"type": "boolean", "description": "True to get lowest-loss (best-performing) feeders instead of highest."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_loss_substations",
            "description": "Rank INDIVIDUAL SUBSTATIONS by average distribution loss % (Substation_Names -- a level between Division and Feeder in the network hierarchy: Division > Substation > Feeder > Transformer). Use only for questions specifically about substations. Do NOT use for Division-level or Feeder-level questions. Produces a bar chart. Uses real production data.",
            "parameters": {
                "type": "object",
                "properties": {
                    **_LOSS_FILTER_PROPS,
                    "n": {"type": "integer", "description": "Number of substations to return (default 10)."},
                    "ascending": {"type": "boolean", "description": "True to get lowest-loss (best-performing) substations instead of highest."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_loss_by_division",
            "description": "Average distribution loss % per Division (Kasna, Urban-I, Urban-II, Surajpur-I, Surajpur-II, Greater Noida West). Use this for any question about which DIVISION/AREA has the highest or lowest loss -- this is the division-level average, not any single feeder's value. Produces a bar chart. Uses real production data.",
            "parameters": {"type": "object", "properties": _LOSS_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_loss_by_dt_type",
            "description": "Average distribution loss % broken down by transformer type (Domestic-Rural, Domestic-Urban, Commercial, Industrial, Agricultural, Institutional, Pump, Street Light). Produces a bar chart. Uses real production data.",
            "parameters": {"type": "object", "properties": _LOSS_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_theft_trend",
            "description": "Get theft cases booked over time (monthly count). Produces a line chart. NOTE: theft data is synthetic placeholder data, not real.",
            "parameters": {"type": "object", "properties": _COMMON_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_theft_by_type",
            "description": "Breakdown of theft cases by Theft_Type (Direct Tapping, Meter Tampering, Bypass, Billing Fraud) with case counts, units stolen and fine amount. Produces a pie chart. NOTE: theft data is synthetic placeholder data, not real.",
            "parameters": {"type": "object", "properties": _COMMON_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_theft_by_status",
            "description": "Breakdown of theft cases by Case_Status (Booked, Under Investigation, Penalty Recovered, Closed). Useful for recovery-rate questions. Produces a bar chart. NOTE: theft data is synthetic placeholder data, not real.",
            "parameters": {"type": "object", "properties": _COMMON_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_theft_feeders",
            "description": "Rank feeders by theft Case_Count, Units_Stolen_kWh, or Fine_Amount_INR. Produces a bar chart. NOTE: theft data is synthetic placeholder data, not real.",
            "parameters": {
                "type": "object",
                "properties": {
                    **_COMMON_FILTER_PROPS,
                    "n": {"type": "integer", "description": "Number of feeders to return (default 10)."},
                    "metric": {"type": "string", "enum": ["Case_Count", "Units_Stolen_kWh", "Fine_Amount_INR"], "description": "Metric to rank by (default Case_Count)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_loss_vs_theft_correlation",
            "description": "Compute the correlation between distribution loss % (real data) and theft (synthetic placeholder data: case count and units stolen), joined monthly per feeder, restricted to feeders present in both datasets. Use this for any question about whether losses and theft are related. Produces a scatter chart.",
            "parameters": {"type": "object", "properties": _COMMON_FILTER_PROPS},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_custom",
            "description": "Fallback for questions that don't fit the other tools: aggregate any numeric column from either dataset, optionally grouped. Use dataset='losses' for real transformer columns (Distribution_Loss_Pct, Energy_Input_kWh, Energy_Billed_kWh, Units_Loss_kWh, Consumer_Count) or dataset='theft' for synthetic theft columns (Units_Stolen_kWh, Fine_Amount_INR).",
            "parameters": {
                "type": "object",
                "properties": {
                    **_LOSS_FILTER_PROPS,
                    "dataset": {"type": "string", "enum": ["losses", "theft"]},
                    "metric": {"type": "string", "description": "Numeric column to aggregate, e.g. 'Distribution_Loss_Pct' or 'Fine_Amount_INR'."},
                    "agg": {"type": "string", "enum": ["sum", "mean", "count", "max", "min"], "description": "Aggregation function (default sum)."},
                    "group_by": {"type": "string", "description": "Optional column to group by, e.g. 'Division', 'Substation_Names', 'Feeder_Name', 'DT_type', 'Theft_Type'."},
                },
                "required": ["dataset", "metric"],
            },
        },
    },
]


def _filters(losses, theft, kwargs):
    division = kwargs.get("division")
    feeder_name = kwargs.get("feeder_name")
    substation_name = kwargs.get("substation_name")
    area_type = kwargs.get("area_type")
    dt_type = kwargs.get("dt_type")
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    fl = A.filter_df(losses, division=division, feeder_name=feeder_name, substation_name=substation_name, area_type=area_type, dt_type=dt_type, date_from=date_from, date_to=date_to)
    ft = A.filter_df(theft, division=division, feeder_name=feeder_name, area_type=area_type, date_from=date_from, date_to=date_to)
    return fl, ft


def _dispatch_uncached(name: str, kwargs: dict, losses: pd.DataFrame, theft: pd.DataFrame):
    """Executes a tool call. Returns (content_for_llm: str, chart_dict_or_none)."""
    fl, ft = _filters(losses, theft, kwargs)

    if name == "get_kpi_summary":
        result = A.kpi_summary(fl, ft)
        return _dumps(result), None

    if name == "get_loss_trend":
        group_by = kwargs.get("group_by")
        df = A.loss_trend(fl, freq="M", group_by=group_by)
        chart = C.fig_loss_trend(df, group_by=group_by)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_top_loss_feeders":
        n = kwargs.get("n", 10)
        asc = kwargs.get("ascending", False)
        df = A.top_loss_feeders(fl, n=n, ascending=asc)
        chart = C.fig_top_loss_feeders(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_top_loss_substations":
        n = kwargs.get("n", 10)
        asc = kwargs.get("ascending", False)
        df = A.top_loss_substations(fl, n=n, ascending=asc)
        chart = C.fig_top_loss_substations(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_loss_by_division":
        df = A.loss_by_division(fl)
        chart = C.fig_loss_by_division(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_loss_by_dt_type":
        df = A.loss_by_dt_type(fl)
        chart = C.fig_loss_by_dt_type(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_theft_trend":
        df = A.theft_trend(ft, freq="M")
        chart = C.fig_theft_trend(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_theft_by_type":
        df = A.theft_by_type(ft)
        chart = C.fig_theft_by_type(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_theft_by_status":
        df = A.theft_by_status(ft)
        chart = C.fig_theft_by_status(df)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_top_theft_feeders":
        n = kwargs.get("n", 10)
        metric = kwargs.get("metric", "Case_Count")
        df = A.top_theft_feeders(ft, n=n, metric=metric)
        chart = C.fig_top_theft_feeders(df, metric=metric)
        return _dumps(_to_records(df)), chart.to_dict()

    if name == "get_loss_vs_theft_correlation":
        result = A.loss_vs_theft_correlation(fl, ft)
        chart = C.fig_loss_vs_theft_scatter(result["data"], y="Case_Count")
        payload = {
            "correlation_loss_vs_case_count": result["correlation_loss_vs_case_count"],
            "correlation_loss_vs_units_stolen": result["correlation_loss_vs_units_stolen"],
            "feeders_in_both_datasets": int(result["data"]["Feeder_Name"].nunique()),
        }
        return _dumps(payload), chart.to_dict()

    if name == "aggregate_custom":
        dataset = kwargs["dataset"]
        metric = kwargs["metric"]
        agg = kwargs.get("agg", "sum")
        group_by = kwargs.get("group_by")
        src_df = fl if dataset == "losses" else ft
        if metric not in src_df.columns:
            return _dumps({"error": f"Unknown column '{metric}' for dataset '{dataset}'."}), None
        df = A.aggregate_metric(src_df, metric=metric, agg=agg, group_by=[group_by] if group_by else None)
        return _dumps(_to_records(df)), None

    return _dumps({"error": f"Unknown tool '{name}'"}), None


# --- TTL cache: the same analytics questions get asked repeatedly across ----
# --- users/sessions, and the underlying data only changes when the -----------
# --- ingestion scripts are re-run, so a short TTL avoids recomputing --------
# --- identical pandas aggregations on every request. -------------------------
_cache_lock = threading.Lock()
_cache: TTLCache = TTLCache(maxsize=512, ttl=TOOL_CACHE_TTL_SECONDS)


def dispatch(name: str, kwargs: dict, losses: pd.DataFrame, theft: pd.DataFrame):
    key = (name, tuple(sorted(kwargs.items())), len(losses), len(theft))
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    result = _dispatch_uncached(name, kwargs, losses, theft)
    with _cache_lock:
        _cache[key] = result
    return result
