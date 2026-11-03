"""Dataset loading, validation, cleaning and profiling (pandas)."""
from __future__ import annotations

import io
import re
from typing import Any

import numpy as np
import pandas as pd

from ..config import get_settings

settings = get_settings()


class DatasetValidationError(ValueError):
    pass


def load_dataframe(path: str) -> pd.DataFrame:
    """Load a stored dataset file back into a DataFrame."""
    if str(path).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    """Parse raw upload bytes into a DataFrame with strict validation."""
    if len(content) == 0:
        raise DatasetValidationError("The uploaded file is empty.")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise DatasetValidationError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB size limit.")

    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise DatasetValidationError(
                "Unsupported file type. Allowed: " + ", ".join(sorted(settings.allowed_extension_set))
            )
    except DatasetValidationError:
        raise
    except Exception as exc:
        raise DatasetValidationError(f"Could not parse the file as a dataset: {type(exc).__name__}") from exc

    return clean_dataframe(df)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic cleaning: safe column names, drop empty rows/cols, limits."""
    if df.empty:
        raise DatasetValidationError("The dataset contains no rows.")

    # Normalize column names: unique, safe strings.
    seen: dict[str, int] = {}
    new_cols = []
    for c in df.columns:
        name = re.sub(r"\s+", "_", str(c).strip()) or "column"
        name = re.sub(r"[^0-9A-Za-z_]+", "", name) or "column"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        new_cols.append(name)
    df = df.copy()
    df.columns = new_cols

    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

    if len(df) == 0 or len(df.columns) == 0:
        raise DatasetValidationError("The dataset is empty after cleaning.")
    if len(df) > settings.MAX_ROWS:
        raise DatasetValidationError(f"Dataset exceeds the {settings.MAX_ROWS:,} row limit.")
    if len(df.columns) > settings.MAX_COLS:
        raise DatasetValidationError(f"Dataset exceeds the {settings.MAX_COLS} column limit.")
    return df


def _is_date_like(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if not pd.api.types.is_object_dtype(series):
        return False
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() >= 0.8)


def _try_parse_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    for col in date_cols:
        parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            df[col] = parsed
    return df


def profile_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return (possibly date-parsed df, JSON-serializable profile)."""
    columns: list[dict[str, Any]] = []
    date_cols: list[str] = []

    for col in df.columns:
        s = df[col]
        info: dict[str, Any] = {
            "name": col,
            "nulls": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(s):
            info["type"] = "numeric"
            info.update(
                min=_num(s.min()), max=_num(s.max()), mean=_num(s.mean()),
                std=_num(s.std()), median=_num(s.median()), sum=_num(s.sum()),
            )
        elif _is_date_like(s):
            info["type"] = "datetime"
            date_cols.append(col)
        else:
            info["type"] = "categorical"
            top = s.astype(str).value_counts().head(5)
            info["top_values"] = [{"value": str(k), "count": int(v)} for k, v in top.items()]
        columns.append(info)

    df = _try_parse_dates(df, date_cols)
    for col in date_cols:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            for info in columns:
                if info["name"] == col:
                    info["min"] = str(df[col].min().date())
                    info["max"] = str(df[col].max().date())

    profile = {
        "rows": int(len(df)),
        "cols": int(len(df.columns)),
        "columns": columns,
        "numeric_columns": [c["name"] for c in columns if c["type"] == "numeric"],
        "date_columns": [c["name"] for c in columns if c["type"] == "datetime"],
        "categorical_columns": [c["name"] for c in columns if c["type"] == "categorical"],
    }
    return df, profile


def _num(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_records(df: pd.DataFrame, limit: int = 50) -> list[dict[str, Any]]:
    out = df.head(limit).copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out = out.replace({np.nan: None})
    return out.to_dict(orient="records")
