"""他ゾーンRDSに対するIS-04 Registration APIクライアント (REQ-E, ⑪4-③)。"""

import logging

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


class NmosRegistrationClient:
    def __init__(self, ip_address: str, port: int, version: str = "v1.3", timeout: float = 5.0):
        self.base_url = f"http://{ip_address}:{port}/x-nmos/registration/{version}"
        self.timeout = timeout

    async def register_resource(self, resource_type: str, data: dict) -> None:
        payload = {"type": resource_type, "data": data}
        url = f"{self.base_url}/resource"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                raise RegistrationApiError("POST", url, resp.status_code, resp.text)

    async def delete_resource(self, resource_type: str, resource_id: str) -> None:
        url = f"{self.base_url}/resource/{resource_type}s/{resource_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(url)
            if resp.status_code >= 400 and resp.status_code != 404:
                raise RegistrationApiError("DELETE", url, resp.status_code, resp.text)

    async def heartbeat(self, node_id: str) -> None:
        url = f"{self.base_url}/health/nodes/{node_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url)
            if resp.status_code >= 400:
                raise RegistrationApiError("POST", url, resp.status_code, resp.text)
