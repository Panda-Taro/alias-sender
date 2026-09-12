"""Alias Nodeの作成管理 (REQ-B01〜B04, ⑨「Alias Nodeの作成管理」)。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas import domain
from app.services.node_port_manager import manager as node_port_manager

router = APIRouter(prefix="/alias-nodes", tags=["alias-nodes"])


@router.get("", response_model=list[domain.AliasNodeOut])
def list_alias_nodes(db: Session = Depends(get_db)):
    return db.query(models.AliasNode).all()


@router.post("", response_model=domain.AliasNodeOut, status_code=201)
async def create_alias_node(payload: domain.AliasNodeIn, db: Session = Depends(get_db)):
    node = models.AliasNode(**payload.model_dump())
    db.add(node)
    db.commit()
    await node_port_manager.sync()
    return node


@router.get("/{node_id}", response_model=domain.AliasNodeOut)
def get_alias_node(node_id: str, db: Session = Depends(get_db)):
    node = db.get(models.AliasNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="AliasNode not found")
    return node


@router.put("/{node_id}", response_model=domain.AliasNodeOut)
async def update_alias_node(node_id: str, payload: domain.AliasNodeIn, db: Session = Depends(get_db)):
    node = db.get(models.AliasNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="AliasNode not found")
    for field, value in payload.model_dump().items():
        setattr(node, field, value)
    db.commit()
    await node_port_manager.sync()
    return node


@router.delete("/{node_id}", status_code=204)
async def delete_alias_node(node_id: str, db: Session = Depends(get_db)):
    node = db.get(models.AliasNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="AliasNode not found")

    # REQ-B04: 紐づいたZoneRdsConfigが存在しないことを削除の条件とする
    linked = db.query(models.ZoneRdsConfig).filter(models.ZoneRdsConfig.node_id == node_id).count()
    if linked > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete AliasNode while ZoneRdsConfig(s) are still linked (REQ-B04)",
        )

    db.delete(node)
    db.commit()
    await node_port_manager.sync()


@router.get("/{node_id}/device-assignments", response_model=list[domain.NodeDeviceAssignmentOut])
def list_device_assignments(node_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.NodeDeviceAssignment)
        .filter(models.NodeDeviceAssignment.node_id == node_id)
        .all()
    )


@router.post("/device-assignments", response_model=domain.NodeDeviceAssignmentOut, status_code=201)
def create_device_assignment(payload: domain.NodeDeviceAssignmentIn, db: Session = Depends(get_db)):
    """X-Yクロスポイント画面: AliasNode(X)とAliasDevice(Y)の紐づけ (REQ-C03)。M:N。"""
    node = db.get(models.AliasNode, payload.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="AliasNode not found")
    device = db.get(models.AliasDevice, payload.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="AliasDevice not found")

    existing = (
        db.query(models.NodeDeviceAssignment)
        .filter(
            models.NodeDeviceAssignment.node_id == payload.node_id,
            models.NodeDeviceAssignment.device_id == payload.device_id,
        )
        .first()
    )
    if existing:
        return existing

    assignment = models.NodeDeviceAssignment(**payload.model_dump())
    db.add(assignment)
    db.commit()
    return assignment


@router.delete("/device-assignments/{assignment_id}", status_code=204)
def delete_device_assignment(assignment_id: str, db: Session = Depends(get_db)):
    assignment = db.get(models.NodeDeviceAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="NodeDeviceAssignment not found")
    db.delete(assignment)
    db.commit()
