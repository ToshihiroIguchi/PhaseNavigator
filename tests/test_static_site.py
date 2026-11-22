"""Tests for the static edition: generated page, browser bundle and server page parity."""
import json
import subprocess
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts import build_static_site as site
from tests.phasecore_data import make_dataset, make_entries


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build the static edition once into a temporary folder."""
    out = tmp_path_factory.mktemp("site")
    warnings = site.build(out)
    return out, warnings


def test_page_has_no_api_key_or_non_commercial_controls(built):
    """The static page needs no key and offers no non-commercial switch."""
    html = (built[0] / "index.html").read_text(encoding="utf-8")

    assert 'data-edition="static"' in html
    assert 'id="api-key"' not in html
    assert 'id="include-non-commercial"' not in html
    assert "not included" in html  # footer states GNoME data is left out
    assert "Bartel et al." in html


def test_page_uses_relative_assets_and_a_pinned_pyodide(built):
    """Assets are relative; Pyodide is pinned and loaded (with its hash) by the worker, not the page."""
    html = (built[0] / "index.html").read_text(encoding="utf-8")

    assert 'src="/' not in html and 'href="/static' not in html
    assert 'src="static/js/static_engine.js' in html
    assert 'src="vendor/plotly.min.js' in html
    assert f'data-pyodide-url="{site.PYODIDE_URL}"' in html
    assert f'data-pyodide-sri="{site.PYODIDE_SRI}"' in html
    assert 'data-worker-url="static/js/calc_worker.js' in html
    assert "pyodide.js" not in html  # the page itself does not load the loader
    for name in ("utils.js", "api.js", "static_engine.js", "calc_worker.js", "ui.js"):
        assert (built[0] / "static" / "js" / name).is_file()
    assert (built[0] / "vendor" / "plotly.min.js").stat().st_size > 1_000_000


def test_worker_checks_the_loader_hash_and_the_site_ships_its_own_server(built):
    """The worker verifies pyodide.mjs against the pinned hash; the folder carries a stdlib-only server."""
    worker = (built[0] / "static" / "js" / "calc_worker.js").read_text(encoding="utf-8")

    assert "integrity: sri" in worker and "pyodide.mjs" in worker
    assert (built[0] / "serve_static.py").read_text(encoding="utf-8") == (
        site.ROOT / "scripts" / "serve_static.py"
    ).read_text(encoding="utf-8")


def test_missing_data_is_reported_as_a_warning(built):
    """Building without downloaded data still works but tells the user what to do."""
    assert any("scripts.build_static_data" in warning for warning in built[1])


def test_zip_is_reproducible_and_complete(tmp_path):
    """The browser bundle contains the code and tables and is byte-for-byte reproducible."""
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    site.write_phasecore_zip(first)
    site.write_phasecore_zip(second)

    assert first.read_bytes() == second.read_bytes()
    names = set(zipfile.ZipFile(first).namelist())
    assert {"phasecore/runtime.py", "phasecore/data/g_els.json", "phasecore/hull.py"} <= names
    assert not any("__pycache__" in name for name in names)


def test_zip_bundle_runs_without_the_repository_or_pymatgen(tmp_path):
    """
    Import the unpacked bundle in a clean interpreter that cannot see pymatgen or the
    repository: that is what the browser has (numpy and scipy only).
    """
    bundle = tmp_path / "bundle"
    with zipfile.ZipFile(_make_zip(tmp_path)) as archive:
        archive.extractall(bundle)
    data_file = tmp_path / "data.json"
    dataset = make_dataset(make_entries())
    data_file.write_text(
        json.dumps({"schema": 1, "fields": list(dataset.meta["fields"]), "entries": dataset.records}),
        encoding="utf-8",
    )
    script = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(bundle)!r})\n"
        "blocked = [m for m in ('pymatgen', 'mp_api', 'fastapi', 'app') if m in sys.modules]\n"
        "assert not blocked, blocked\n"
        "import phasecore.runtime as rt\n"
        f"rt.load_dataset('GGA_GGA_U', open({str(data_file)!r}, encoding='utf-8').read())\n"
        "out = json.loads(rt.run(json.dumps({'formulas': ['Fe', 'Al', 'O'], 'temperature': 1000, "
        "'e_cut': 0.2, 'functional': 'GGA_GGA_U'})))\n"
        "assert out['ok'], out\n"
        "assert 'pymatgen' not in sys.modules\n"
        "print(out['result']['metadata']['num_phases'])\n"
    )
    # -I keeps the repository (current directory) and user site-packages off the path.
    result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) >= 5


def _make_zip(tmp_path):
    """Write the bundle zip into a temporary folder and return its path."""
    target = tmp_path / "phasecore.zip"
    site.write_phasecore_zip(target)
    return target


def test_runtime_returns_errors_as_data():
    """User-facing problems come back as {"ok": false} so the page can show them."""
    from phasecore import runtime

    runtime._DATASETS["GGA_GGA_U"] = make_dataset(make_entries())
    try:
        bad = json.loads(runtime.run(json.dumps(
            {"formulas": ["Fe", "Ac"], "temperature": 1000, "e_cut": 0.2, "functional": "GGA_GGA_U"})))
        missing = json.loads(runtime.run(json.dumps(
            {"formulas": ["Fe", "O"], "temperature": 0, "e_cut": 0.2, "functional": "R2SCAN"})))
    finally:
        runtime._DATASETS.clear()

    assert bad == {"ok": False, "error": "Finite-temperature data is not available for Ac. Use 0 K or remove these elements."}
    assert missing["ok"] is False and "No data is loaded" in missing["error"]


def test_data_scope_limits_the_elements():
    """A build that covers only some elements says so instead of returning nothing."""
    from phasecore import generate_diagram

    dataset = make_dataset(make_entries())
    dataset.meta["scope"] = ["Al", "Fe", "O"]

    with pytest.raises(ValueError, match="covers only Al, Fe, O. Remove C"):
        generate_diagram(dataset, ["Fe", "C"], 0, 0.2, "GGA_GGA_U")


def test_server_page_is_unchanged_by_the_static_templates():
    """The server edition still shows the API key field and loads assets from /static."""
    html = TestClient(app).get("/").text

    assert 'id="api-key"' in html
    assert 'id="include-non-commercial"' in html
    assert 'src="/static/js/ui.js' in html
    assert 'src="/vendor/plotly.min.js' in html
    assert "data-edition" not in html
    assert "pyodide" not in html.lower()
