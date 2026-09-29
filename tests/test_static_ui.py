"""Serve the built UI without exposing application data or changing API routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from rag_agent.api import create_app
from rag_agent.config import Settings


def test_built_ui_assets_and_api_boundaries(tmp_path: Path) -> None:
    ui = tmp_path / "static"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text('<html><script src="/assets/main.js"></script></html>')
    (ui / "assets" / "main.js").write_text("console.log('UI');")
    (ui / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    (tmp_path / "private.json").write_text('{"secret": "private"}')
    application = create_app(Settings(_env_file=None), agent=object(), static_dir=ui)
    with TestClient(application) as client:
        response = client.get("/")
        assert response.status_code == 200 and "/assets/main.js" in response.text
        policy = response.headers["Content-Security-Policy"]
        assert "script-src 'self'" in policy and "connect-src 'self'" in policy
        assert "font-src 'self'" in policy and "object-src 'none'" in policy
        assert client.get("/assets/main.js").status_code == 200
        assert client.get("/favicon.svg").status_code == 200
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/v1/missing").status_code == 404
        assert client.get("/private.json").status_code == 404
        assert client.get("/assets/%2e%2e/%2e%2e/private.json").status_code == 404


def test_unbuilt_ui_keeps_functional_fallback(tmp_path: Path) -> None:
    with TestClient(
        create_app(Settings(_env_file=None), agent=object(), static_dir=tmp_path)
    ) as client:
        response = client.get("/")
        assert response.status_code == 200 and 'id="form"' in response.text
        assert client.get("/assets/missing.js").status_code == 404
