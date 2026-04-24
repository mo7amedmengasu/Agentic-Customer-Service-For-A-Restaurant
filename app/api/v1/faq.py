import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQResponse
from app.my_agent.tools.faq_tools import get_embedding
from app.my_agent.agents.faq_agent import faq_agent



router = APIRouter(prefix="/faqs", tags=["FAQs"])

@router.post("/", response_model=FAQResponse)
def create_faq(faq: FAQCreate, db: Session = Depends(get_db)):
    vector=get_embedding(faq.question)  #This could be changed for a cleaner implementation, but for now it's fine to have it here.

    db_faq=FAQ(
        question=faq.question,
        answer=faq.answer,
        embedding=json.dumps(vector)
    )
    
    db.add(db_faq)
    db.commit()
    db.refresh(db_faq)
    return db_faq

@router.get("/", response_model=List[FAQResponse])
def get_faqs(db: Session = Depends(get_db)):
    return db.query(FAQ).all()




@router.post("/ask")
def ask(question: str, db: Session = Depends(get_db)):

    result = faq_agent(
        {
            "user_message": str(question),
            "faq": None,
            "response": None,
            "tool_result": None
        },
        db
    )

    return {
        "question": question,
        "answer": result.get("response"),
        "matched_faq_score": (
            result.get("tool_result", {}).get("score")
            if result.get("tool_result")
            else None
        )
    }