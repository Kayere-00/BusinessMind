"""Dataset upload, validation, listing, preview and deletion — org-scoped."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import admin_only, analyst_or_admin, get_current_user
from ..models import Dataset, User
from ..schemas import DatasetOut
from ..services import profiling, storage

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
settings = get_settings()


def _get_org_dataset(db: Session, dataset_id: str, org_id: str) -> Dataset:
    ds = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == org_id))
    if ds is None:
        # 404 (not 403) — never reveal that another tenant's resource exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found.")
    return ds


@router.post("", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile,
    name: str | None = Query(default=None, max_length=200),
    current: User = Depends(analyst_or_admin),
    db: Session = Depends(get_db),
):
    original = storage.sanitize_filename(file.filename or "upload")
    ext = Path(original).suffix.lower()
    if ext not in settings.allowed_extension_set:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(settings.allowed_extension_set))}",
        )

    content = await file.read()
    try:
        df = profiling.parse_upload(original, content)
    except profiling.DatasetValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    df, profile = profiling.profile_dataframe(df)

    stored = storage.new_stored_path(current.org_id, original, ext=".csv")
    df.to_csv(stored, index=False)

    ds = Dataset(
        org_id=current.org_id,
        name=(name or Path(original).stem)[:200],
        original_filename=original,
        stored_path=str(stored),
        row_count=int(len(df)),
        col_count=int(len(df.columns)),
        profile=profile,
        uploaded_by=current.id,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.get("", response_model=list[DatasetOut])
def list_datasets(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Dataset).where(Dataset.org_id == current.org_id).order_by(Dataset.created_at.desc())
    ).all()
    return rows


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_org_dataset(db, dataset_id, current.org_id)


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    n: int = Query(default=50, ge=1, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ds = _get_org_dataset(db, dataset_id, current.org_id)
    path = storage.resolve_within(ds.stored_path, current.org_id)
    df = profiling.load_dataframe(str(path))
    return {"columns": list(df.columns), "rows": profiling.to_records(df, limit=n)}


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, current: User = Depends(admin_only), db: Session = Depends(get_db)):
    ds = _get_org_dataset(db, dataset_id, current.org_id)
    try:
        path = storage.resolve_within(ds.stored_path, current.org_id)
        path.unlink(missing_ok=True)
    except PermissionError:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Storage error.") from None
    db.delete(ds)
    db.commit()
