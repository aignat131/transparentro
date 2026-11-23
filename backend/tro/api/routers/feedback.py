from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tro.api import schemas as S
from tro.db import get_db
from tro.models import CorrectionRequest

router = APIRouter(tags=["corecții"])


@router.post("/corrections", response_model=S.Message, status_code=201, summary="Trimite o cerere de corecție")
def submit_correction(body: S.CorrectionIn, db: Session = Depends(get_db)):
    db.add(CorrectionRequest(email=body.email, entity_url=body.entity_url, message=body.message))
    db.commit()
    return S.Message(message="Mulțumim! Cererea de corecție a fost înregistrată și va fi analizată.")
