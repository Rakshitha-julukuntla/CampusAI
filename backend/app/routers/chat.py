import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, rag, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatOut)
def chat(body: schemas.ChatIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    recent = (db.query(models.ChatHistory)
              .filter(models.ChatHistory.user_id == user.id)
              .order_by(models.ChatHistory.created_at.desc())
              .limit(4).all())
    history = [{"question": h.question, "answer": h.answer} for h in reversed(recent)]

    try:
        result = rag.answer_question(body.question, history=history, category=body.category)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM/retrieval error: {e}")

    db.add(models.ChatHistory(user_id=user.id, question=body.question,
                              answer=result["answer"], sources=json.dumps(result["sources"])))
    db.commit()
    return result


@router.get("/history", response_model=list[schemas.HistoryItem])
def history(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(models.ChatHistory)
            .filter(models.ChatHistory.user_id == user.id)
            .order_by(models.ChatHistory.created_at.asc())
            .limit(100).all())
    return [{"id": r.id, "question": r.question, "answer": r.answer,
             "sources": json.loads(r.sources or "[]"), "created_at": r.created_at} for r in rows]


@router.delete("/history")
def clear_history(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.ChatHistory).filter(models.ChatHistory.user_id == user.id).delete()
    db.commit()
    return {"ok": True}
