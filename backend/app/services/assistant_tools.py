"""Validated, read-only analytics tools exposed to the local language model."""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import analysis, forecasting


class _ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArgs(_ToolArgs):
    pass


class MetricArgs(_ToolArgs):
    metric: str | None = Field(default=None, max_length=100)


class TrendArgs(MetricArgs):
    frequency: str = Field(default="M", pattern="^(D|W|M|Q)$")


class BreakdownArgs(MetricArgs):
    group_by: str = Field(min_length=1, max_length=100)
    top_n: int = Field(default=8, ge=1, le=10)


class ForecastArgs(MetricArgs):
    periods: int = Field(default=6, ge=1, le=24)


class RatioArgs(_ToolArgs):
    numerator: str = Field(min_length=1, max_length=100)
    denominator: str = Field(min_length=1, max_length=100)


class CompareArgs(_ToolArgs):
    metric: str = Field(min_length=1, max_length=100)
    date_column: str = Field(min_length=1, max_length=100)
    period_a_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_a_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_b_start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    period_b_end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ReportArgs(_ToolArgs):
    title: str = Field(min_length=3, max_length=200)


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "inspect_dataset",
            "description": "Inspect dataset columns, types, missing values and aggregate ranges. Never returns raw rows.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_kpis",
            "description": "Calculate deterministic summary KPIs from the selected dataset.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_ratio",
            "description": "Calculate a deterministic percentage ratio between two numeric columns, such as profit divided by revenue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "numerator": {"type": "string", "description": "Exact numeric column name in the numerator."},
                    "denominator": {"type": "string", "description": "Exact numeric column name in the denominator."},
                },
                "required": ["numerator", "denominator"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_trend",
            "description": "Aggregate a numeric metric over time using the selected date column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Exact numeric column name; omit for the default metric."},
                    "frequency": {"type": "string", "enum": ["D", "W", "M", "Q"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_breakdown",
            "description": "Group and sum a numeric metric by an exact categorical dataset column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {"type": "string", "description": "Exact dataset column to group by."},
                    "metric": {"type": "string", "description": "Exact numeric column; omit for the default metric."},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": "Detect statistical outliers. Returns counts only, not individual records.",
            "parameters": {
                "type": "object",
                "properties": {"metric": {"type": "string", "description": "Exact numeric column; omit for the default metric."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_correlations",
            "description": "Calculate correlations between numeric columns.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forecast_metric",
            "description": "Forecast a numeric metric by month, with model error and prediction intervals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Exact numeric column; omit for the default metric."},
                    "periods": {"type": "integer", "minimum": 1, "maximum": 24},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_periods",
            "description": "Compare deterministic sums for two explicit date ranges in the dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Exact numeric column name."},
                    "date_column": {"type": "string", "description": "Exact datetime column name."},
                    "period_a_start": {"type": "string", "description": "Inclusive YYYY-MM-DD date."},
                    "period_a_end": {"type": "string", "description": "Inclusive YYYY-MM-DD date."},
                    "period_b_start": {"type": "string", "description": "Inclusive YYYY-MM-DD date."},
                    "period_b_end": {"type": "string", "description": "Inclusive YYYY-MM-DD date."},
                },
                "required": [
                    "metric", "date_column", "period_a_start", "period_a_end",
                    "period_b_start", "period_b_end",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_report",
            "description": "Propose a PDF report for user confirmation. This tool never creates or downloads a report.",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string", "minLength": 3, "maxLength": 200}},
                "required": ["title"],
            },
        },
    },
]

ARGUMENT_MODELS: dict[str, type[_ToolArgs]] = {
    "inspect_dataset": EmptyArgs,
    "calculate_kpis": EmptyArgs,
    "calculate_ratio": RatioArgs,
    "analyze_trend": TrendArgs,
    "analyze_breakdown": BreakdownArgs,
    "detect_anomalies": MetricArgs,
    "analyze_correlations": EmptyArgs,
    "forecast_metric": ForecastArgs,
    "compare_periods": CompareArgs,
    "request_report": ReportArgs,
}


class ToolInputError(ValueError):
    pass


def available_tools(*, can_create_report: bool) -> list[dict[str, Any]]:
    if can_create_report:
        return TOOL_DEFINITIONS
    return [tool for tool in TOOL_DEFINITIONS if tool["function"]["name"] != "request_report"]


def _column(df: pd.DataFrame, name: str, *, numeric: bool = False, date: bool = False) -> str:
    if name not in df.columns:
        raise ToolInputError(f"Unknown column '{name}'. Inspect the dataset and use an exact column name.")
    if numeric and not pd.api.types.is_numeric_dtype(df[name]):
        raise ToolInputError(f"Column '{name}' is not numeric.")
    if date and not pd.api.types.is_datetime64_any_dtype(df[name]):
        raise ToolInputError(f"Column '{name}' is not a date column.")
    return name


def _inspect_dataset(df: pd.DataFrame) -> dict[str, Any]:
    columns = []
    for name in df.columns:
        values = df[name]
        item: dict[str, Any] = {
            "name": str(name)[:100],
            "type": str(values.dtype),
            "missing": int(values.isna().sum()),
            "unique_values": int(values.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(values) and not _sensitive_column(str(name)):
            item.update(
                minimum=_clean_number(values.min()),
                maximum=_clean_number(values.max()),
                mean=_clean_number(values.mean()),
                total=_clean_number(values.sum()),
            )
        elif pd.api.types.is_datetime64_any_dtype(values):
            item["earliest"] = str(values.min().date()) if values.notna().any() else None
            item["latest"] = str(values.max().date()) if values.notna().any() else None
        columns.append(item)
    return {"rows": int(len(df)), "columns": columns}


def _sensitive_column(name: str) -> bool:
    return bool(re.search(
        r"email|phone|mobile|address|ssn|social.?security|(^|_)(id|uuid)(_|$)|"
        r"first.?name|last.?name|full.?name|customer.?name|client.?name|person.?name|"
        r"contact.?name|customer.?id|user.?id|account.?number",
        name,
        re.IGNORECASE,
    ))


def _clean_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _compare_periods(df: pd.DataFrame, args: CompareArgs) -> dict[str, Any]:
    metric = _column(df, args.metric, numeric=True)
    date_column = _column(df, args.date_column, date=True)
    ranges = [
        (args.period_a_start, args.period_a_end, "period_a"),
        (args.period_b_start, args.period_b_end, "period_b"),
    ]
    results: dict[str, Any] = {"metric": metric, "date_column": date_column}
    for start_text, end_text, key in ranges:
        try:
            start = pd.Timestamp(start_text)
            end = pd.Timestamp(end_text) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
        except (TypeError, ValueError) as exc:
            raise ToolInputError("Date ranges must use valid YYYY-MM-DD dates.") from exc
        if start > end:
            raise ToolInputError(f"{key} starts after it ends.")
        values = df.loc[df[date_column].between(start, end), metric]
        results[key] = {
            "start": start_text,
            "end": end_text,
            "total": _clean_number(values.sum()),
            "rows": int(values.notna().sum()),
        }
    a = results["period_a"]["total"]
    b = results["period_b"]["total"]
    results["change_pct"] = round((b - a) / abs(a) * 100, 2) if a else None
    return results


def execute_tool(
    name: str,
    arguments: Any,
    df: pd.DataFrame,
    *,
    can_create_report: bool,
    dataset_id: str | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Validate a model-requested operation and run only a registered tool."""
    model = ARGUMENT_MODELS.get(name)
    if model is None:
        raise ToolInputError("This tool is not available.")
    if not isinstance(arguments, dict):
        raise ToolInputError("Tool arguments must be a JSON object.")
    try:
        args = model.model_validate(arguments)
    except ValidationError as exc:
        raise ToolInputError("Invalid tool arguments: " + "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )) from exc

    actions: list[dict[str, str]] = []
    if name == "inspect_dataset":
        result = _inspect_dataset(df)
    elif name == "calculate_kpis":
        result = analysis.compute_kpis(df)
    elif name == "calculate_ratio":
        assert isinstance(args, RatioArgs)
        numerator = _column(df, args.numerator, numeric=True)
        denominator = _column(df, args.denominator, numeric=True)
        paired = df[[numerator, denominator]].dropna()
        numerator_total = _clean_number(paired[numerator].sum())
        denominator_total = _clean_number(paired[denominator].sum())
        result = {
            "numerator": numerator,
            "denominator": denominator,
            "numerator_total": numerator_total,
            "denominator_total": denominator_total,
            "ratio_pct": (
                round(numerator_total / denominator_total * 100, 2)
                if numerator_total is not None and denominator_total not in (None, 0)
                else None
            ),
            "rows": int(len(paired)),
        }
    elif name == "analyze_trend":
        assert isinstance(args, TrendArgs)
        if args.metric:
            _column(df, args.metric, numeric=True)
        result = analysis.compute_timeseries(df, args.metric, args.frequency)
        if result.get("available") and len(result.get("points", [])) > 120:
            result["points"] = result["points"][-120:]
            result["truncated"] = True
    elif name == "analyze_breakdown":
        assert isinstance(args, BreakdownArgs)
        group_by = _column(df, args.group_by)
        if _sensitive_column(group_by):
            raise ToolInputError("This column may contain personal identifiers; group by a non-identifying column instead.")
        if pd.api.types.is_numeric_dtype(df[group_by]):
            raise ToolInputError("Choose a categorical column for grouping.")
        metric = args.metric or analysis.pick_primary_metric(df)
        if not metric:
            raise ToolInputError("The dataset has no numeric metric.")
        _column(df, metric, numeric=True)
        result = analysis.compute_breakdown(df, group_by, metric, args.top_n)
    elif name == "detect_anomalies":
        assert isinstance(args, MetricArgs)
        metric = args.metric or analysis.pick_primary_metric(df)
        if not metric:
            raise ToolInputError("The dataset has no numeric metric.")
        _column(df, metric, numeric=True)
        raw_result = analysis.compute_anomalies(df, metric)
        result = {key: value for key, value in raw_result.items() if key != "anomalies"}
    elif name == "analyze_correlations":
        result = analysis.compute_correlations(df)
    elif name == "forecast_metric":
        assert isinstance(args, ForecastArgs)
        if args.metric:
            _column(df, args.metric, numeric=True)
        result = forecasting.forecast_metric(df, args.metric, args.periods)
        if len(result.get("history", [])) > 120:
            result["history"] = result["history"][-120:]
            result["history_truncated"] = True
    elif name == "compare_periods":
        assert isinstance(args, CompareArgs)
        result = _compare_periods(df, args)
    elif name == "request_report":
        assert isinstance(args, ReportArgs)
        if not can_create_report:
            raise ToolInputError("Your role cannot create reports.")
        title = re.sub(r"\s+", " ", args.title).strip()
        if len(title) < 3:
            raise ToolInputError("Report title must contain at least three characters.")
        result = {"confirmation_required": True, "title": title}
        actions.append({"type": "confirm_report", "title": title, "dataset_id": dataset_id or ""})
    else:
        raise ToolInputError("This tool is not available.")

    return result, actions
