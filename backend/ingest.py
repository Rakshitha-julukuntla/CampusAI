"""
Bulk-load every document in backend/data/ into ChromaDB.

Usage (from backend/ with venv active):
    python ingest.py            # ingest / update everything in data/
    python ingest.py --reset    # wipe the vector DB first, then ingest
"""
import shutil
import sys
from pathlib import Path

from app.config import settings
from app.database import Base, SessionLocal, engine
from app import rag
from app.routers.documents import sync_documents


def main():
    if "--reset" in sys.argv and Path(settings.CHROMA_DIR).exists():
        shutil.rmtree(settings.CHROMA_DIR)
        print(f"Deleted {settings.CHROMA_DIR}")

    print(f"Loading embedding model {settings.EMBEDDING_MODEL} (first run downloads it)...")
    print(f"Ingesting documents from {settings.DATA_DIR} ...")
    report = rag.ingest_directory()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        sync_documents(db, report)
    finally:
        db.close()

    print(f"\nDone: {len(report)} files, {sum(report.values())} chunks stored in {settings.CHROMA_DIR}")
    empty = [f for f, n in report.items() if n == 0]
    if empty:
        print("WARNING - no text extracted (scanned PDFs? run OCR):", *empty, sep="\n  ")


if __name__ == "__main__":
    main()
