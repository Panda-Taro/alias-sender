"""他ゾーンRDSに対するIS-04 Registration APIクライアント (REQ-E, ⑪4-③)。"""

import logging

import httpx

logger = logging.getLogger(__name__)


class NmosRegistrationClient:
    def __init__(self, ip_address: str, port: int, version: str = "v1.3", timeout: float = 5.0):
        self.base_url = f"http://{ip_address}:{port}/x-nmos/registration/{version}"
        self.timeout = timeout

    async def register_resource(self, resource_type: str, data: dict) -> None:
        payload = {"type": resource_type, "data": data}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/resource", json=payload)
            resp.raise_for_status()

    async def delete_resource(self, resource_type: str, resource_id: str) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(f"{self.base_url}/resource/{resource_type}s/{resource_id}")
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

    async def heartbeat(self, node_id: str) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/health/nodes/{node_id}")
            resp.raise_for_status()
