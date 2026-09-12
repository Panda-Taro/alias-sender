"""Alias Sender設定 (REQ-D01〜D08, ⑨「Alias Sender設定」メニュー)。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas import domain
from app.services.alias_sender_logic import AliasSenderError, create_alias_sender, update_alias_sender_connector

router = APIRouter(tags=["alias-senders"])


@router.get("/real-senders", response_model=list[domain.RealSenderOut])
def list_real_senders(
    label_contains: str | None = None,
    media_type: domain.MediaType | None = None,
    db: Session = Depends(get_db),
):
    """REQ-D01: 文字列フィルター・media_typeフィルターに対応したReal Sender選択用一覧。"""
    query = db.query(models.RealSender)
    if label_contains:
        query = query.filter(models.RealSender.nmos_sender_label.ilike(f"%{label_contains}%"))
    if media_type:
        query = query.filter(models.RealSender.media_type_detected == media_type)
    return query.all()


@router.get("/real-senders/{real_sender_id}", response_model=domain.RealSenderDetailOut)
def get_real_sender(real_sender_id: str, db: Session = Depends(get_db)):
    real_sender = db.get(models.RealSender, real_sender_id)
    if real_sender is None:
        raise HTTPException(status_code=404, detail="RealSender not found")
    return real_sender


@router.get("/alias-senders", response_model=list[domain.AliasSenderOut])
def list_alias_senders(connector_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.AliasSender)
    if connector_id:
        query = query.filter(models.AliasSender.connector_id == connector_id)
    return query.all()


@router.get("/alias-senders/{alias_sender_id}", response_model=domain.AliasSenderDetailOut)
def get_alias_sender(alias_sender_id: str, db: Session = Depends(get_db)):
    alias_sender = db.get(models.AliasSender, alias_sender_id)
    if alias_sender is None:
        raise HTTPException(status_code=404, detail="AliasSender not found")
    return alias_sender


@router.post("/alias-senders", response_model=domain.AliasSenderOut, status_code=201)
def create_alias_sender_endpoint(payload: domain.AliasSenderCreateIn, db: Session = Depends(get_db)):
    try:
        alias_sender = create_alias_sender(
            db,
            connector_id=payload.connector_id,
            real_sender_id=payload.real_sender_id,
            media_type=payload.media_type,
            description=payload.description,
        )
        db.commit()
    except AliasSenderError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return alias_sender


@router.put("/alias-senders/{alias_sender_id}", response_model=domain.AliasSenderOut)
def update_alias_sender_endpoint(alias_sender_id: str, payload: domain.AliasSenderUpdateIn, db: Session = Depends(get_db)):
    alias_sender = db.get(models.AliasSender, alias_sender_id)
    if alias_sender is None:
        raise HTTPException(status_code=404, detail="AliasSender not found")

    try:
        if payload.connector_id and payload.connector_id != alias_sender.connector_id:
            # REQ-D02: 紐づけ先Connectorの変更
            update_alias_sender_connector(db, alias_sender, payload.connector_id)
        if payload.description is not None:
            # REQ-D06: descriptionは紐づけ後も変更可能
            alias_sender.description = payload.description
        if payload.media_type is not None:
            # REQ-D05: media_typeはユーザーが独立して上書き可能(以後Real側に追従しない)
            duplicate = (
                db.query(models.AliasSender)
                .filter(
                    models.AliasSender.connector_id == alias_sender.connector_id,
                    models.AliasSender.media_type == payload.media_type,
                    models.AliasSender.id != alias_sender.id,
                )
                .first()
            )
            if duplicate:
                raise AliasSenderError(f"Connector already has a {payload.media_type} AliasSender")
            alias_sender.media_type = payload.media_type
        db.commit()
    except AliasSenderError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return alias_sender


@router.delete("/alias-senders/{alias_sender_id}", status_code=204)
def delete_alias_sender_endpoint(alias_sender_id: str, db: Session = Depends(get_db)):
    alias_sender = db.get(models.AliasSender, alias_sender_id)
    if alias_sender is None:
        raise HTTPException(status_code=404, detail="AliasSender not found")
    db.delete(alias_sender)
    db.commit()
