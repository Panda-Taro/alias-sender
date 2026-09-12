"""AliasNodeごとのNode API/Connection APIサブアプリがCORSを許可することを
確認する (NMOS ExplorerのようなブラウザベースツールがP2PでNode APIへ直接
アクセスする際、CORSヘッダーが無いと「Cannot connect」に見える不具合の
再発防止、DECISIONS.md参照)。
"""

from fastapi.testclient import TestClient

from app.nmos.node_app import create_node_app


def test_node_app_sets_cors_headers():
    app = create_node_app("node-1")
    client = TestClient(app)

    response = client.get(
        "/x-nmos/node/v1.3/receivers",
        headers={"Origin": "http://example.com"},
    )
    assert response.headers.get("access-control-allow-origin") == "*"


def test_node_app_handles_cors_preflight():
    app = create_node_app("node-1")
    client = TestClient(app)

    response = client.options(
        "/x-nmos/node/v1.3/receivers",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
