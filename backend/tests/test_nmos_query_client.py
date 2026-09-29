"""Query APIのページネーション対応の回帰テスト。

RDS上の登録件数がページ上限を超えると、`Link`ヘッダで次ページが案内される
(RFC5988)。これを辿らないと一部のリソースだけが返り、正常なReal Senderが
一時的にofflineへ誤検知される不具合があった。
"""

import httpx
import pytest

from app.services.nmos_query_client import NmosQueryClient, _next_page_url


def test_next_page_url_extracts_rel_next():
    header = '<http://rds/x-nmos/query/v1.3/senders?paging.since=100>; rel="next"'
    assert _next_page_url(header) == "http://rds/x-nmos/query/v1.3/senders?paging.since=100"


def test_next_page_url_ignores_other_rels():
    header = (
        '<http://rds/senders?paging.since=1>; rel="first", '
        '<http://rds/senders?paging.since=2>; rel="prev"'
    )
    assert _next_page_url(header) is None


def test_next_page_url_none_when_no_header():
    assert _next_page_url(None) is None


@pytest.mark.asyncio
async def test_get_senders_follows_pagination(monkeypatch):
    page1_url = "http://10.0.0.1:3210/x-nmos/query/v1.3/senders"
    page2_url = "http://10.0.0.1:3210/x-nmos/query/v1.3/senders?paging.since=1"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == page1_url:
            return httpx.Response(
                200,
                json=[{"id": "s1"}],
                headers={"Link": f'<{page2_url}>; rel="next"'},
            )
        if str(request.url) == page2_url:
            return httpx.Response(200, json=[{"id": "s2"}])
        raise AssertionError(f"unexpected URL requested: {request.url}")

    transport = httpx.MockTransport(handler)

    real_async_client = httpx.AsyncClient

    def patched_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_async_client)

    client = NmosQueryClient("10.0.0.1", 3210, "v1.3")
    senders = await client.get_senders()

    assert [s["id"] for s in senders] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_get_senders_single_page_without_link_header(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "s1"}, {"id": "s2"}])

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_async_client)

    client = NmosQueryClient("10.0.0.1", 3210, "v1.3")
    senders = await client.get_senders()

    assert [s["id"] for s in senders] == ["s1", "s2"]
