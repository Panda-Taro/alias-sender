import logging
import logging.handlers
from pathlib import Path

from app.config import settings


class _SuppressManagementApiAccessLogs(logging.Filter):
    """`uvicorn.access`はメインWebGUI(/api/...)とAliasNodeごとのNode/Connection
    API(/x-nmos/...)の両方でリクエストごとに1行出力する。WebGUI側は
    ダッシュボードのポーリングで数秒おきに大量のアクセスログを出すため、
    NMOSコントローラー等からの実際の疎通(/x-nmos/配下)を追いやすくする目的で
    /api/へのアクセスログのみ抑制する(他ゾーンコントローラーとの相互接続
    トラブルシューティングのため、⑬NFR-03)。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/api/" not in message


def setup_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.log_level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # 管理API(/api/...)への定期ポーリングでログが埋まらないようにしつつ、
    # NMOS API(/x-nmos/...)への外部からのアクセスはINFOで記録し続ける。
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.INFO)
    access_logger.addFilter(_SuppressManagementApiAccessLogs())
