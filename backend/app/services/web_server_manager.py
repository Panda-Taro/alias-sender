"""WebGUI/管理API自体の待受ポートを動的に変更できるようにするマネージャー。

AliasNodeごとのNode APIサーバー(node_port_manager)と同じ考え方で、メインの
FastAPIアプリ(WebGUI + 管理REST API)自体もuvicorn.Serverをasyncioタスクとして
自前で起動・停止する。これにより、システム設定画面からのポート変更を、
コンテナ再起動なしに反映できる。
"""

import asyncio
import logging

import uvicorn

logger = logging.getLogger(__name__)


class WebServerManager:
    def __init__(self) -> None:
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None
        self.port: int | None = None

    async def start(self, port: int) -> None:
        from app.main import app  # 遅延importで循環importを回避

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", loop="asyncio")
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        self._server, self._task, self.port = server, task, port
        logger.info("WebGUI/management API server started on port %d", port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.should_exit = True
        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except asyncio.TimeoutError:
            self._task.cancel()
        self._server = None
        self._task = None
        logger.info("WebGUI/management API server stopped (was on port %s)", self.port)

    async def restart(self, new_port: int) -> None:
        await self.stop()
        await self.start(new_port)


manager = WebServerManager()
