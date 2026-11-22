"""Tests for the standard-library web server that ships with the static edition."""
import threading
import urllib.request

import pytest

from scripts import serve_static as server_module


@pytest.fixture()
def site(tmp_path):
    """A tiny site folder with one file of each kind the page needs."""
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "static" / "js").mkdir(parents=True)
    (tmp_path / "static" / "js" / "calc_worker.js").write_text("// worker", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "entries.json.gz").write_bytes(b"\x1f\x8b\x08\x00data")
    (tmp_path / "phasecore.zip").write_bytes(b"PK\x03\x04")
    return tmp_path


@pytest.fixture()
def running(site):
    """Serve the site on a free local port while a test runs."""
    httpd = server_module.make_server(site, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def fetch(port, path):
    """Return (status, headers, body) of a local request."""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
        return response.status, response.headers, response.read()


def test_mime_types_do_not_depend_on_the_system(running):
    """Workers need text/javascript; data files are plain bytes (no Content-Encoding)."""
    _, js, _ = fetch(running, "/static/js/calc_worker.js")
    _, data, body = fetch(running, "/data/entries.json.gz")
    _, archive, _ = fetch(running, "/phasecore.zip")

    assert js["Content-Type"].startswith("text/javascript")
    assert data["Content-Type"] == "application/gzip"
    assert data["Content-Encoding"] is None
    assert body.startswith(b"\x1f\x8b")
    assert archive["Content-Type"] == "application/zip"


def test_pages_and_scripts_are_revalidated(running):
    """A new build is never hidden by a stale browser cache."""
    _, html, _ = fetch(running, "/")
    _, js, _ = fetch(running, "/static/js/calc_worker.js?v=1.0.0")
    _, data, _ = fetch(running, "/data/entries.json.gz")

    assert html["Cache-Control"] == "no-cache"
    assert js["Cache-Control"] == "no-cache"
    assert data["Cache-Control"] is None


def test_listens_on_this_computer_only_unless_lan_is_requested(site, monkeypatch, capsys):
    """Without --lan the server binds 127.0.0.1; with --lan it binds every interface."""
    bound = []

    def fake_make_server(directory, host, port):
        bound.append(host)

        class Fake:
            server_address = (host, 8080)

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                pass

        return Fake()

    monkeypatch.setattr(server_module, "make_server", fake_make_server)
    monkeypatch.setattr(server_module, "lan_addresses", lambda: ["192.168.0.5"])

    assert server_module.main(["--dir", str(site)]) == 0
    assert "Only this computer" in capsys.readouterr().out
    assert server_module.main(["--dir", str(site), "--lan"]) == 0
    assert "http://192.168.0.5:8080/" in capsys.readouterr().out
    assert bound == ["127.0.0.1", "0.0.0.0"]


def test_missing_site_data_and_busy_port_are_explained(site, tmp_path_factory, capsys):
    """A site without data warns; a missing site or a busy port stops with a clear message."""
    empty = tmp_path_factory.mktemp("empty")
    assert server_module.main(["--dir", str(empty)]) == 1
    assert "Build the site first" in capsys.readouterr().err

    httpd = server_module.make_server(site, "127.0.0.1", 0)
    try:
        port = httpd.server_address[1]
        assert server_module.main(["--dir", str(site), "--port", str(port)]) == 1
        err = capsys.readouterr().err
    finally:
        httpd.server_close()
    assert "warning" in err and "manifest.json" in err
    assert "Try another port" in err
