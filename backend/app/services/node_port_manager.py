"""AliasNodeごとのNode API/Connection APIサーバーの動的起動・停止を管理する
(⑪1, REQ-F01)。

各AliasNodeにnode_api_portで割り当てられたuvicorn.Serverをasyncioタスクとして
個別に立て、node_api_enabled/node_api_portの変更に追従して再起動する。
"""

import asyncio
import logging

import uvicorn

from app.db import models
from app.db.database import get_session
from app.nmos.node_app import create_node_app

logger = logging.getLogger(__name__)


class _RunningServer:
    def __init__(self, server: uvicorn.Server, task: asyncio.Task, port: int):
        self.server = server
        self.task = task
        self.port = port


class NodePortServerManager:
    def __init__(self) -> None:
        self._servers: dict[str, _RunningServer] = {}

    async def sync(self) -> None:
        """DBの現在の状態に合わせて、各AliasNodeのサーバーを起動/停止/再起動する。"""
        db = get_session()
        try:
            nodes = db.query(models.AliasNode).all()
            desired: dict[str, int] = {
                n.id: n.node_api_port
                for n in nodes
                if n.node_api_enabled and n.node_api_port
            }
        finally:
            db.close()

        # Stop servers that are no longer desired, or whose port changed
        for node_id in list(self._servers.keys()):
            if node_id not in desired or self._servers[node_id].port != desired[node_id]:
                await self._stop(node_id)

        # Start servers newly desired
        for node_id, port in desired.items():
            if node_id not in self._servers:
                await self._start(node_id, port)

    async def stop_all(self) -> None:
        for node_id in list(self._servers.keys()):
            await self._stop(node_id)

    async def _start(self, node_id: str, port: int) -> None:
        app = create_node_app(node_id)
        # log_config=None: uvicornが独自にlogging.config.dictConfig()を実行して
        # uvicorn.access/uvicorn.errorのハンドラ・フィルタを上書きしてしまうのを防ぎ、
        # app.logging_configで設定したルートロガー(ファイル出力含む)にそのまま
        # 委譲する。動的Node APIサーバーはNodeの作成/削除の都度何度も再生成
        # されるため、log_configを渡したままだと毎回ロギング設定が上書きされる。
        config = uvicorn.Config(
            app, host="0.0.0.0", port=port, log_level="info", loop="asyncio", log_config=None
        )
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        self._servers[node_id] = _RunningServer(server, task, port)
        logger.info("Started Node/Connection API server for AliasNode %s on port %d", node_id, port)

    async def _stop(self, node_id: str) -> None:
        running = self._servers.pop(node_id, None)
        if running is None:
            return
        running.server.should_exit = True
        try:
            await asyncio.wait_for(running.task, timeout=5.0)
        except asyncio.TimeoutError:
            running.task.cancel()
        logger.info("Stopped Node/Connection API server for AliasNode %s", node_id)


manager = NodePortServerManager()
