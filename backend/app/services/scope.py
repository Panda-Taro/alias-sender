"""AliasNodeスコープの解決 (⑪3, REQ-F02〜F04, REQ-E02)。

NodeDeviceAssignmentがM:Nであるため、「どのAliasNodeから見るか」によって
見えるDevice/Connector/Sender/Sourceの範囲が変わる。Node APIとRegistration API
の双方がこのロジックを共有する。
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from app.db import models


@dataclass
class NodeScope:
    node: models.AliasNode
    devices: list[models.AliasDevice] = field(default_factory=list)
    connectors: list[models.AliasConnector] = field(default_factory=list)
    senders: list[models.AliasSender] = field(default_factory=list)


def get_node_scope(db: Session, node_id: str) -> NodeScope | None:
    node = db.get(models.AliasNode, node_id)
    if node is None:
        return None

    assignments = (
        db.query(models.NodeDeviceAssignment)
        .filter(models.NodeDeviceAssignment.node_id == node_id)
        .all()
    )
    device_ids = [a.device_id for a in assignments]
    if not device_ids:
        return NodeScope(node=node, devices=[], connectors=[], senders=[])

    devices = (
        db.query(models.AliasDevice)
        .filter(models.AliasDevice.id.in_(device_ids))
        .all()
    )
    connectors = (
        db.query(models.AliasConnector)
        .filter(models.AliasConnector.device_id.in_(device_ids))
        .options(joinedload(models.AliasConnector.senders))
        .all()
    )
    senders: list[models.AliasSender] = []
    for c in connectors:
        senders.extend(c.senders)

    return NodeScope(node=node, devices=devices, connectors=connectors, senders=senders)


def find_sender_in_scope(scope: NodeScope, sender_id: str) -> models.AliasSender | None:
    for s in scope.senders:
        if s.id == sender_id:
            return s
    return None
