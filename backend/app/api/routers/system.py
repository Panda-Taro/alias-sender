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
from app.db.database import Base, engine, get_db, get_session, reopen_engine
from app.schemas import domain
from app.services import registration_engine, same_zone_sync
from app.services.host_info import get_os_ip_addresses
from app.services.node_port_manager import manager as node_port_manager
from app.services.web_server_manager import manager as web_server_manager
from app.nmos import resources as nmos_resources

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


@router.post("/reset")
async def reset_database():
    """WebGUI「システム設定」の「初期化」: AliasNode/Device/Connector/Sender、
    RDS設定、Real Senderキャッシュ等を全て削除する。

    WebGUIの待受ポート設定(SystemSettings)は、この操作で接続不能になるのを
    避けるため保持する。
    """
    db = get_session()
    try:
        settings_row = db.query(models.SystemSettings).first()
        preserved_web_port = settings_row.web_port if settings_row else settings.web_port
    finally:
        db.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = get_session()
    try:
        db.add(models.SystemSettings(web_port=preserved_web_port))
        db.commit()
    finally:
        db.close()

    # バックグラウンドエンジンのインメモリ状態も合わせて初期化する
    registration_engine.zone_status.clear()
    registration_engine.engine._registered_sender_ids.clear()
    registration_engine.engine._last_sent_version.clear()
    nmos_resources._version_cache.clear()
    same_zone_sync.status = same_zone_sync.SameZoneStatus()
    await node_port_manager.sync()

    logger.warning("System reset: all AliasNode/Device/Connector/Sender/RDS configuration has been deleted")
    return {"status": "ok", "message": "Database has been reset. The WebGUI port setting was preserved."}


@router.get("/logs")
def get_logs(lines: int = 100):
    """WebGUI「システム設定」の「ログ表示」: 最新N件のログ行を返す(NFR-03)。"""
    log_path = Path(settings.log_dir) / "app.log"
    if not log_path.is_file():
        return {"lines": []}
    all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": all_lines[-lines:]}


@router.get("/logs/download")
def download_logs():
    log_path = Path(settings.log_dir) / "app.log"
    return FileResponse(path=log_path, filename="app.log", media_type="text/plain")
