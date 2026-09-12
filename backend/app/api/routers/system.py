"""システム設定 (REQ-H08, H09, ⑨「システム設定」メニュー)。"""

import asyncio
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.db.database import get_db, reopen_engine
from app.schemas import domain
from app.services.host_info import get_os_ip_addresses
from app.services.web_server_manager import manager as web_server_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=domain.SystemInfoOut)
def system_info(db: Session = Depends(get_db)):
    row = db.query(models.SystemSettings).first()
    return domain.SystemInfoOut(
        os_ip_addresses=get_os_ip_addresses(),
        web_port=row.web_port if row else (web_server_manager.port or settings.web_port),
        node_api_port_start=settings.node_api_port_start,
    )


@router.put("/web-port")
async def update_web_port(payload: domain.WebPortIn, db: Session = Depends(get_db)):
    """WebGUI/管理APIの待受ポートを変更する。プロセス再起動は不要。

    このリクエスト自体は旧ポートのサーバーで処理されているため、切り替えは
    レスポンスを返した直後にバックグラウンドで行う(このリクエストの完了を
    待たずに旧サーバーをシャットダウンするとデッドロックするため)。
    """
    row = db.query(models.SystemSettings).first()
    if row is None:
        row = models.SystemSettings(web_port=payload.web_port)
        db.add(row)
    else:
        row.web_port = payload.web_port
    db.commit()

    async def _delayed_restart() -> None:
        await asyncio.sleep(0.2)
        await web_server_manager.restart(payload.web_port)

    asyncio.create_task(_delayed_restart())
    return {
        "status": "ok",
        "message": f"WebGUI is restarting on port {payload.web_port}. Reconnect using the new port shortly.",
    }


@router.get("/db/export")
def export_db():
    """REQ-H08: SQLiteファイル(.db)そのものをダウンロードする。"""
    db_path = Path(settings.db_path)
    return FileResponse(path=db_path, filename="alias_sender.db", media_type="application/octet-stream")


@router.post("/db/import")
async def import_db(file: UploadFile):
    """REQ-H08: アップロードされたSQLiteファイルで現在のDBを置き換える。

    PoCの簡易実装のため、アップロード後は再起動を推奨する(README参照)。
    """
    db_path = Path(settings.db_path)
    tmp_path = db_path.with_suffix(".uploading")
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    tmp_path.replace(db_path)
    reopen_engine()
    return {"status": "ok", "message": "Database imported. A container restart is recommended to fully re-sync background engines."}
