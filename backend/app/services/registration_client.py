"""他ゾーンRDSに対するIS-04 Registration APIクライアント (REQ-E, ⑪4-③)。"""

import asyncio
import http.client
import json
import logging
import socket

import httpx

logger = logging.getLogger(__name__)


class RegistrationApiError(Exception):
    """RDSからの4xx/5xx応答を、ボディ(schema検証エラー詳細等)付きで表現する。

    `resp.raise_for_status()`が返す標準の例外メッセージにはURLとステータス
    コードしか含まれず、nmos-cpp等が返すJSON schema検証エラーの詳細本文が
    失われてログ/ダッシュボードから見えなくなってしまうため、本文を含めて
    再送出する。
    """

    def __init__(self, method: str, url: str, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        snippet = body.strip().replace("\n", " ")[:300]
        super().__init__(f"{method} {url} -> HTTP {status_code}: {snippet}")


def _connect_with_source_port(host: str, port: int, source_port: int, timeout: float) -> socket.socket:
    """指定した送信元ポートにbindした上でTCP接続を確立する (REQ-E07)。

    httpx/httpcoreは送信元IPアドレスの固定(local_address)には対応しているが、
    送信元ポート番号の固定には対応していないため、標準ライブラリのsocketで
    低レベルに接続を確立する。ハートビート等で同じポートから短い間隔で
    接続を繰り返すため、TIME_WAIT状態の影響を受けないようSO_REUSEADDRを
    付与する。
    """
    last_exc: OSError | None = None
    for family, socktype, proto, _canonname, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
    ):
        sock = socket.socket(family, socktype, proto)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", source_port))
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            sock.close()
            last_exc = exc
    assert last_exc is not None
    raise last_exc


class _BoundHTTPConnection(http.client.HTTPConnection):
    """指定の送信元ポートからのみ接続するhttp.client.HTTPConnection。"""

    def __init__(self, host: str, port: int, source_port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._source_port = source_port

    def connect(self) -> None:
        self.sock = _connect_with_source_port(self.host, self.port, self._source_port, self.timeout)


def _sync_request_with_source_port(
    method: str, host: str, port: int, path: str, source_port: int, timeout: float, body: bytes | None
) -> tuple[int, str]:
    conn = _BoundHTTPConnection(host, port, source_port, timeout)
    try:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", errors="replace")
        return resp.status, text
    finally:
        conn.close()


class NmosRegistrationClient:
    def __init__(
        self,
        ip_address: str,
        port: int,
        version: str = "v1.3",
        timeout: float = 5.0,
        source_port: int | None = None,
    ):
        self.ip_address = ip_address
        self.port = port
        self.path_prefix = f"/x-nmos/registration/{version}"
        self.base_url = f"http://{ip_address}:{port}{self.path_prefix}"
        self.timeout = timeout
        self.source_port = source_port
        if source_port is not None:
            logger.info(
                "NmosRegistrationClient for %s:%s will bind to fixed source port %s (REQ-E07)",
                ip_address,
                port,
                source_port,
            )

    async def _request(self, method: str, path: str, json_body: dict | None = None) -> tuple[int, str]:
        if self.source_port is not None:
            body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
            return await asyncio.to_thread(
                _sync_request_with_source_port,
                method,
                self.ip_address,
                self.port,
                path,
                self.source_port,
                self.timeout,
                body,
            )
        url = f"http://{self.ip_address}:{self.port}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(method, url, json=json_body)
            return resp.status_code, resp.text

    async def register_resource(self, resource_type: str, data: dict) -> None:
        payload = {"type": resource_type, "data": data}
        path = f"{self.path_prefix}/resource"
        status, text = await self._request("POST", path, payload)
        if status >= 400:
            raise RegistrationApiError("POST", f"{self.base_url}/resource", status, text)

    async def delete_resource(self, resource_type: str, resource_id: str) -> None:
        path = f"{self.path_prefix}/resource/{resource_type}s/{resource_id}"
        status, text = await self._request("DELETE", path)
        if status >= 400 and status != 404:
            raise RegistrationApiError(
                "DELETE", f"{self.base_url}/resource/{resource_type}s/{resource_id}", status, text
            )

    async def heartbeat(self, node_id: str) -> None:
        path = f"{self.path_prefix}/health/nodes/{node_id}"
        status, text = await self._request("POST", path)
        if status >= 400:
            raise RegistrationApiError("POST", f"{self.base_url}/health/nodes/{node_id}", status, text)
