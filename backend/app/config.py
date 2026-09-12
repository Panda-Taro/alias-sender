from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALIAS_", env_file=".env", extra="ignore")

    # WebGUI / REST management API port (REQ-H)
    web_port: int = 8000

    # Default starting port for dynamically-allocated AliasNode Node/Connection API servers
    node_api_port_start: int = 10080

    # SQLite database file location (mounted volume in docker-compose)
    db_path: str = "data/alias_sender.db"

    # Heartbeat interval for Registration API (IS-04 standard, ⑪5)
    heartbeat_interval_seconds: float = 5.0

    # Polling fallback interval for same-zone RDS Query API (in addition to WebSocket)
    query_poll_interval_seconds: float = 30.0

    log_dir: str = "logs"
    log_level: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file.as_posix()}"


settings = Settings()
