"""In-process cache for the reference DataFrames. Loaded once and reused
across requests; automatically reloads if the underlying Excel file changes
on disk (mtime check), so re-running the ingestion scripts doesn't require an
app restart.

Reading a ~37k-row .xlsx via openpyxl takes ~30s -- too slow for a cold
start. A Parquet sidecar cache (regenerated whenever the .xlsx is newer than
it) makes subsequent loads near-instant.
"""
import os
import threading

import pandas as pd

from app.config import TRANSFORMER_LOSSES_PATH, THEFT_CASES_PATH

_lock = threading.Lock()
_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _load(path: str) -> pd.DataFrame:
    parquet_path = os.path.splitext(path)[0] + ".parquet"
    if os.path.exists(parquet_path) and os.path.getmtime(parquet_path) >= os.path.getmtime(path):
        return pd.read_parquet(parquet_path)

    df = pd.read_excel(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df.to_parquet(parquet_path, index=False)
    return df


def _get_cached(path: str) -> pd.DataFrame:
    mtime = os.path.getmtime(path)
    with _lock:
        cached = _cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
    df = _load(path)
    with _lock:
        _cache[path] = (mtime, df)
    return df


def get_transformer_losses() -> pd.DataFrame:
    return _get_cached(TRANSFORMER_LOSSES_PATH)


def get_theft_cases() -> pd.DataFrame:
    return _get_cached(THEFT_CASES_PATH)


def warm_cache():
    get_transformer_losses()
    get_theft_cases()
