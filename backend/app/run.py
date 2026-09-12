"""コンテナのエントリーポイント。

`uvicorn app.main:app`をCLIから直接起動する代わりに、自前でuvicorn.Serverを
asyncioタスクとして管理する(`web_server_manager`)ことで、WebGUIのシステム設定
画面からポート番号を変更した際に、プロセスを再起動せずにリスニングポートを
差し替えられるようにする。
"""

import asyncio
import logging
import signal

from app.config import settings
from app.db import models
from app.db.database import get_session, init_db
from app.logging_config import setup_logging
from app.services.web_server_manager import manager as web_server_manager

setup_logging()
logger = logging.getLogger(__name__)


def _initial_port() -> int:
    init_db()
    db = get_session()
    try:
        row = db.query(models.SystemSettings).first()
        if row is None:
            row = models.SystemSettings(web_port=settings.web_port)
            db.add(row)
            db.commit()
        return row.web_port
    finally:
        db.close()


async def main() -> None:
    port = _initial_port()
    await web_server_manager.start(port)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, AttributeError):
            # Windows等、add_signal_handler未対応の環境ではフォールバック
            pass

    try:
        await stop_event.wait()
    finally:
        await web_server_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
