"""Alias Device / Alias Connectorの作成管理 (REQ-C01〜C03, ⑨「Alias Device/Connectorの作成管理」)。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas import domain

router = APIRouter(tags=["alias-devices"])


@router.get("/alias-devices", response_model=list[domain.AliasDeviceOut])
def list_alias_devices(db: Session = Depends(get_db)):
    return db.query(models.AliasDevice).all()


@router.post("/alias-devices", response_model=domain.AliasDeviceOut, status_code=201)
def create_alias_device(payload: domain.AliasDeviceIn, db: Session = Depends(get_db)):
    device = models.AliasDevice(**payload.model_dump())
    db.add(device)
    db.commit()
    return device


@router.put("/alias-devices/{device_id}", response_model=domain.AliasDeviceOut)
def update_alias_device(device_id: str, payload: domain.AliasDeviceIn, db: Session = Depends(get_db)):
    device = db.get(models.AliasDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="AliasDevice not found")
    device.alias_device_label = payload.alias_device_label
    device.alias_device_description = payload.alias_device_description
    db.commit()
    return device


@router.delete("/alias-devices/{device_id}", status_code=204)
def delete_alias_device(device_id: str, db: Session = Depends(get_db)):
    device = db.get(models.AliasDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="AliasDevice not found")
    db.delete(device)
    db.commit()


@router.get("/alias-connectors", response_model=list[domain.AliasConnectorOut])
def list_alias_connectors(device_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.AliasConnector)
    if device_id:
        query = query.filter(models.AliasConnector.device_id == device_id)
    return query.all()


@router.post("/alias-connectors", response_model=domain.AliasConnectorOut, status_code=201)
def create_alias_connector(payload: domain.AliasConnectorIn, db: Session = Depends(get_db)):
    device = db.get(models.AliasDevice, payload.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="AliasDevice not found")
    connector = models.AliasConnector(**payload.model_dump())
    db.add(connector)
    db.commit()
    return connector


@router.put("/alias-connectors/{connector_id}", response_model=domain.AliasConnectorOut)
def update_alias_connector(connector_id: str, connector_label: str, db: Session = Depends(get_db)):
    connector = db.get(models.AliasConnector, connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="AliasConnector not found")
    connector.connector_label = connector_label
    db.commit()
    return connector


@router.delete("/alias-connectors/{connector_id}", status_code=204)
def delete_alias_connector(connector_id: str, db: Session = Depends(get_db)):
    connector = db.get(models.AliasConnector, connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="AliasConnector not found")
    db.delete(connector)
    db.commit()
