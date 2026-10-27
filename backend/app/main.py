from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .auth import hash_password
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import auth, chat, documents


def _create_admin():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL).first():
            db.add(models.User(name="Admin", email=settings.ADMIN_EMAIL,
                               password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin"))
            db.commit()
            print(f"[startup] Created admin user: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates MySQL tables if missing
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    _create_admin()
    yield


app = FastAPI(title="CampusAI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.GEMINI_MODEL, "embeddings": settings.EMBEDDING_MODEL}
