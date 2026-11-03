"""PDF report generation, listing and download — org-scoped."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import admin_only, analyst_or_admin, get_current_user
from ..models import Report, User
from ..schemas import ReportCreateRequest, ReportOut
from ..services import profiling, reporting, storage
from .datasets import _get_org_dataset

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=201)
def create_report(payload: ReportCreateRequest, current: User = Depends(analyst_or_admin), db: Session = Depends(get_db)):
    ds = _get_org_dataset(db, payload.dataset_id, current.org_id)
    path = storage.resolve_within(ds.stored_path, current.org_id)
    df = profiling.load_dataframe(str(path))
    df, _ = profiling.profile_dataframe(df)

    out_path = storage.new_stored_path(current.org_id, "report", sub="reports", ext=".pdf")
    org_name = current.organization.name if current.organization else "Organization"
    reporting.generate_report(df, payload.title.strip(), ds.name, org_name, out_path)

    report = Report(
        org_id=current.org_id, dataset_id=ds.id, title=payload.title.strip(),
        stored_path=str(out_path), created_by=current.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Report).where(Report.org_id == current.org_id).order_by(Report.created_at.desc())
    ).all()


def _get_org_report(db: Session, report_id: str, org_id: str) -> Report:
    rep = db.scalar(select(Report).where(Report.id == report_id, Report.org_id == org_id))
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return rep


@router.get("/{report_id}/download")
def download_report(report_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rep = _get_org_report(db, report_id, current.org_id)
    path = storage.resolve_within(rep.stored_path, current.org_id)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report file is missing.")
    safe_title = storage.sanitize_filename(rep.title)
    return FileResponse(path, media_type="application/pdf", filename=f"{safe_title}.pdf")


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: str, current: User = Depends(admin_only), db: Session = Depends(get_db)):
    rep = _get_org_report(db, report_id, current.org_id)
    storage.resolve_within(rep.stored_path, current.org_id).unlink(missing_ok=True)
    db.delete(rep)
    db.commit()
