import json

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_frontend_index_served():
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert "SmartRoute" in resp.text
    # Verify PWA meta tags and manifest link
    assert 'rel="manifest" href="manifest.webmanifest"' in resp.text
    assert 'apple-touch-icon' in resp.text
    assert 'navigator.serviceWorker.register' in resp.text
    # Verify Mobile Bottom Sheet elements
    assert 'sheet-handle-bar' in resp.text
    assert 'data-sheet-state' in resp.text
    # Verify Simulated data banner preserved
    assert 'SIMULATED DATA' in resp.text
    # Verify Scenario map visualization functions & elements
    assert 'updateScenarioOverlay' in resp.text
    assert 'updateLegend' in resp.text
    assert 'map-legend-content' in resp.text
    assert 'incident-marker-pill' in resp.text
    assert '/scenarios/overlay' in resp.text

def test_pwa_manifest_served():
    resp = client.get("/app/manifest.webmanifest")
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data["name"] == "SmartRoute — Emergency Route Optimizer"
    assert data["short_name"] == "SmartRoute"
    assert data["display"] == "standalone"
    assert len(data["icons"]) >= 3
    # Check icons have valid sizes and purposes
    sizes = [icon["sizes"] for icon in data["icons"]]
    assert "192x192" in sizes
    assert "512x512" in sizes

def test_service_worker_served():
    resp = client.get("/app/sw.js")
    assert resp.status_code == 200
    content = resp.text
    # Verify critical rules in SW:
    # 1. Network-only bypass for API requests
    assert "isApiRequest" in content
    assert "/route" in content
    # 2. 503 response if backend is unreachable
    assert "503" in content
    assert "Backend unavailable" in content

def test_pwa_icons_served():
    resp_192 = client.get("/app/icons/icon-192.png")
    assert resp_192.status_code == 200
    assert resp_192.content.startswith(b"\x89PNG\r\n\x1a\n")

    resp_512 = client.get("/app/icons/icon-512.png")
    assert resp_512.status_code == 200
    assert resp_512.content.startswith(b"\x89PNG\r\n\x1a\n")

    resp_svg = client.get("/app/icons/icon.svg")
    assert resp_svg.status_code == 200
    assert "<svg" in resp_svg.text
