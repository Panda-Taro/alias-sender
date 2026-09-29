"""同一ゾーンRDSに対するIS-04 Query APIクライアント (REQ-A01/A02, ⑪4-①)。

本システムはRDS機能を持たないため、Query APIは常にクライアント側として動作する。
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class NmosQueryClient:
    def __init__(self, ip_address: str, port: int, version: str = "v1.3", timeout: float = 5.0):
        self.base_url = f"http://{ip_address}:{port}/x-nmos/query/{version}"
        self.timeout = timeout

    async def get_nodes(self) -> list[dict]:
        return await self._get_list("/nodes")

    async def get_devices(self) -> list[dict]:
        return await self._get_list("/devices")

    async def get_senders(self) -> list[dict]:
        return await self._get_list("/senders")

    async def get_sender(self, sender_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/senders/{sender_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    async def fetch_manifest(self, manifest_href: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(manifest_href)
            resp.raise_for_status()
            return resp.text

    async def create_subscription(self, ws_base_ip: str | None = None) -> dict:
        """sendersリソースを対象にWebSocket subscriptionを作成する (⑪4-②)"""
        payload = {
            "max_update_rate_ms": 100,
            "resource_path": "/senders",
            "params": {},
            "persist": False,
            "secure": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/subscriptions", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def _get_list(self, path: str) -> list[dict]:
        """IS-04 Query APIのページネーション(`Link`ヘッダ, RFC5988)に対応した全件取得。

        RDS上の登録件数がページ上限を超えると1回のGETでは一部しか返らず、
        たまたまそのtickで漏れたリソースを「消失した」と誤検知してしまう
        (同一ゾーンRDS連携でReal Senderが実際は正常なのに一時的にofflineへ
        倒れる不具合の原因だった)。`rel="next"`を無くなるまで辿って全件を
        結合する。
        """
        results: list[dict] = []
        url: str | None = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while url:
                resp = await client.get(url)
                resp.raise_for_status()
                results.extend(resp.json())
                url = _next_page_url(resp.headers.get("Link"))
        return results


def _next_page_url(link_header: str | None) -> str | None:
    """`Link`ヘッダから`rel="next"`のURLを取り出す。無ければNone。"""
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip()
        if not (url.startswith("<") and url.endswith(">")):
            continue
        params = [seg.strip() for seg in segments[1:]]
        if any(p in ('rel="next"', "rel=next") for p in params):
            return url[1:-1]
    return None
