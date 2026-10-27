import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, rag, schemas
from ..auth import require_admin
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/documents", tags=["documents"])

CATEGORIES = ["general", "admissions", "fees", "academics", "examinations", "departments",
              "placements", "facilities", "student_life", "policies", "notices"]
MAX_MB = 25


def _safe_name(name: str) -> str:
    name = os.path.basename(name)
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


@router.get("/categories")
def categories():
    return CATEGORIES


@router.get("", response_model=list[schemas.DocumentOut])
def list_docs(_: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(models.Document).order_by(models.Document.uploaded_at.desc()).all()


@router.post("/upload", response_model=schemas.DocumentOut)
async def upload(file: UploadFile = File(...), category: str = Form("general"),
                 admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    filename = _safe_name(file.filename or "upload")
    ext = Path(filename).suffix.lower()
    if ext not in rag.SUPPORTED_EXT:
        raise HTTPException(400, f"Unsupported file type {ext}. Use PDF, TXT or MD.")
    if category not in CATEGORIES:
        category = "general"

    content = await file.read()
    if len(content) > MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"File larger than {MAX_MB} MB")

    dest_dir = Path(settings.DATA_DIR) / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(content)

    try:
        n = rag.ingest_file(dest, category)
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {e}")
    if n == 0:
        raise HTTPException(400, "No text could be extracted. If this is a scanned PDF, run OCR on it first.")

    doc = db.query(models.Document).filter(models.Document.filename == filename).first()
    if doc:
        doc.chunks, doc.category = n, category
    else:
        doc = models.Document(filename=filename, category=category, chunks=n, uploaded_by=admin.id)
        db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{doc_id}")
def delete_doc(doc_id: int, _: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    rag.delete_source(doc.filename)
    path = Path(settings.DATA_DIR) / doc.category / doc.filename
    if path.exists():
        path.unlink()
    db.delete(doc)
    db.commit()
    return {"ok": True}


def sync_documents(db: Session, report: dict) -> None:
    """Make sure every file ingested from data/ also appears in the documents table."""
    for rel_path, n in report.items():
        p = Path(rel_path)
        category = p.parent.name if str(p.parent) not in ("", ".") else "general"
        doc = db.query(models.Document).filter(models.Document.filename == p.name).first()
        if doc:
            doc.chunks, doc.category = n, category
        else:
            db.add(models.Document(filename=p.name, category=category, chunks=n))
    db.commit()


@router.post("/reindex")
def reindex(_: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """Re-ingest every file inside backend/data/ (useful after copying files in manually)."""
    report = rag.ingest_directory()
    sync_documents(db, report)
    return {"files": len(report), "chunks": sum(report.values()), "report": report}


@router.get("/stats")
def stats(_: models.User = Depends(require_admin)):
    return rag.collection_stats()
