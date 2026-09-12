"""システム設定 (REQ-H08, H09, ⑨「システム設定」メニュー)。"""

import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.db.database import reopen_engine
from app.schemas import domain
from app.services.host_info import get_os_ip_addresses

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=domain.SystemInfoOut)
def system_info():
    return domain.SystemInfoOut(
        os_ip_addresses=get_os_ip_addresses(),
        web_port=settings.web_port,
        node_api_port_start=settings.node_api_port_start,
    )


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
