"""Analytics endpoints — every figure is computed from the org's own dataset."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..services import analysis, forecasting, profiling, storage
from .datasets import _get_org_dataset

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _load_org_df(db: Session, dataset_id: str, org_id: str):
    ds = _get_org_dataset(db, dataset_id, org_id)
    path = storage.resolve_within(ds.stored_path, org_id)
    df = profiling.load_dataframe(str(path))
    # Re-apply date parsing so time-series endpoints work on reload.
    df, _ = profiling.profile_dataframe(df)
    return df


@router.get("/{dataset_id}/kpis")
def kpis(dataset_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _load_org_df(db, dataset_id, current.org_id)
    return analysis.compute_kpis(df)


@router.get("/{dataset_id}/timeseries")
def timeseries(
    dataset_id: str,
    metric: str | None = Query(default=None, max_length=100),
    freq: str = Query(default="M", pattern="^[DWMQ]$"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_org_df(db, dataset_id, current.org_id)
    return analysis.compute_timeseries(df, metric, freq)


@router.get("/{dataset_id}/breakdown")
def breakdown(
    dataset_id: str,
    by: str | None = Query(default=None, max_length=100),
    metric: str | None = Query(default=None, max_length=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_org_df(db, dataset_id, current.org_id)
    return analysis.compute_breakdown(df, by, metric)


@router.get("/{dataset_id}/anomalies")
def anomalies(
    dataset_id: str,
    metric: str | None = Query(default=None, max_length=100),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    df = _load_org_df(db, dataset_id, current.org_id)
    return analysis.compute_anomalies(df, metric)


@router.get("/{dataset_id}/correlations")
def correlations(dataset_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _load_org_df(db, dataset_id, current.org_id)
    return analysis.compute_correlations(df)


@router.get("/{dataset_id}/forecast")
def forecast(
    dataset_id: str,
    metric: str | None = Query(default=None, max_length=100),
    periods: int = Query(default=6, ge=1, le=24),
    current: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    df = _load_org_df(db, dataset_id, current.org_id)
    result = forecasting.forecast_metric(df, metric, periods)
    if not result.get("available"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result.get("reason"))
    return result


@router.get("/{dataset_id}/insights")
def insights(dataset_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = _load_org_df(db, dataset_id, current.org_id)
    return {"insights": analysis.compute_insights(df)}
