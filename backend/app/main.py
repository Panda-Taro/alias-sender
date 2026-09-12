import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import alias_devices, alias_nodes, alias_senders, dashboard, rds_config, system
from app.db.database import init_db
from app.logging_config import setup_logging
from app.services import registration_engine, same_zone_sync
from app.services.node_port_manager import manager as node_port_manager

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await node_port_manager.sync()
    await same_zone_sync.engine.start()
    await registration_engine.engine.start()
    logger.info("Alias Unit Server started")
    yield
    await same_zone_sync.engine.stop()
    await registration_engine.engine.stop()
    await node_port_manager.stop_all()
    logger.info("Alias Unit Server stopped")


app = FastAPI(title="Alias Unit Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rds_config.router, prefix="/api")
app.include_router(alias_nodes.router, prefix="/api")
app.include_router(alias_devices.router, prefix="/api")
app.include_router(alias_senders.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 本番Dockerイメージではビルド済みのReact SPAを`static/`配下に配置し、
# WebGUIとREST管理APIを同一ポート(ALIAS_WEB_PORT)で提供する。
# フロントエンドはZabbix風の単一ページ(左メニューで表示切替)のため
# クライアントサイドルーティングのフォールバックは不要。
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
