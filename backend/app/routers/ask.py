from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import QueryLog, User
from ..providers.llm import get_provider
from ..security import current_user, require_patient
from ..services.ask import answer_question
from ..services.evaluation import latest_report, run_evaluation
from ..services.present import iso

router = APIRouter(prefix="/api", tags=["ask"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    tz: int = 330


@router.post("/ask")
def ask(body: AskIn, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return answer_question(db, user, body.question, tz=body.tz)


@router.get("/ask/history")
def history(user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = (db.query(QueryLog).filter(QueryLog.user_id == user.id, QueryLog.source == "app")
            .order_by(QueryLog.created_at.desc()).limit(30).all())
    return [{"id": r.id, "question": r.question, "answer": r.answer, "refused": r.refused,
             "created_at": iso(r.created_at)} for r in rows]


@router.post("/eval/run")
def eval_run(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Runs Corpus B on a fresh synthetic persona. Never touches real users' memories."""
    return run_evaluation(db)


@router.get("/eval/latest")
def eval_latest(user: User = Depends(current_user)):
    report = latest_report()
    if not report:
        raise HTTPException(404, "No evaluation has been run since the server started.")
    return report


@router.get("/health")
def health():
    p = get_provider()
    return {"ok": True, "provider": p.name, "geocoder": settings.GEOCODER,
            "database": settings.DATABASE_URL.split(":")[0]}
